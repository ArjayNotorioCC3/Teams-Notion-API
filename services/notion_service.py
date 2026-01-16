"""Notion API service for ticket creation."""
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
import httpx
from config import settings

logger = logging.getLogger(__name__)

NOTION_API_BASE = "https://api.notion.com/v1"

# Connection pool settings for better performance
CONNECTION_LIMIT = 5
TIMEOUT = 30.0


class NotionService:
    """Service for interacting with Notion API."""
    
    def __init__(self):
        """Initialize the Notion service with connection pooling."""
        self.database_id = settings.notion_database_id
        self.api_token = settings.notion_api_token
        self.headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
            "Notion-Version": "2022-06-28"
        }
        
        # Create persistent httpx client with connection pooling
        # This reuses connections and reduces TCP handshake overhead
        self._http_client = httpx.Client(
            limits=httpx.Limits(
                max_connections=CONNECTION_LIMIT,
                max_keepalive_connections=CONNECTION_LIMIT,
                keepalive_expiry=300.0
            ),
            timeout=TIMEOUT
        )
        
        # Cache for Notion user IDs (email -> user_id mapping)
        self._user_id_cache: Dict[str, str] = {}
        
        logger.info(f"NotionService initialized with connection pooling (max={CONNECTION_LIMIT})")
    
    def _get_user_id_by_email(self, email: str) -> Optional[str]:
        """
        Get Notion user ID by email address.
        
        Lists Notion workspace users and finds matching email.
        Results are cached for performance.
        
        Args:
            email: User email address (case-insensitive)
            
        Returns:
            Notion user ID or None if not found
        """
        email_lower = email.lower()
        
        # Check cache first
        if email_lower in self._user_id_cache:
            return self._user_id_cache[email_lower]
        
        try:
            # List all users in the workspace
            response = self._make_request("GET", "/users")
            users = response.get("results", [])
            
            # Search for user by email (case-insensitive)
            for user in users:
                user_email = None
                if user.get("type") == "person":
                    person = user.get("person", {})
                    user_email = person.get("email", "").lower()
                elif user.get("type") == "bot":
                    # Skip bots
                    continue
                
                if user_email == email_lower:
                    user_id = user.get("id")
                    if user_id:
                        # Cache the result
                        self._user_id_cache[email_lower] = user_id
                        logger.debug(f"Found Notion user ID for {email}: {user_id}")
                        return user_id
            
            logger.warning(f"Notion user not found for email: {email}")
            return None
        except Exception as e:
            logger.warning(f"Could not get Notion user ID for {email}: {str(e)}")
            return None
    
    def _build_people_property(self, email: str) -> Dict[str, Any]:
        """
        Build a Notion people property from an email address.
        
        Attempts to find the Notion user ID by email. If not found,
        returns an empty people array (property will be empty).
        
        Args:
            email: User email address
            
        Returns:
            Notion people property dictionary
        """
        user_id = self._get_user_id_by_email(email)
        if user_id:
            return {
                "people": [
                    {
                        "id": user_id
                    }
                ]
            }
        else:
            # Return empty people array if user not found
            logger.warning(f"Could not find Notion user for {email}, leaving people property empty")
            return {
                "people": []
            }
    
    def __del__(self):
        """Cleanup httpx client on destruction."""
        if hasattr(self, '_http_client'):
            self._http_client.close()
            logger.debug("NotionService httpx client closed")
    
    def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Make an authenticated request to Notion API.
        
        Uses persistent httpx client with connection pooling for better performance.
        
        Args:
            method: HTTP method (GET, POST, PATCH, etc.)
            endpoint: API endpoint (relative to base URL)
            data: Request body data
            
        Returns:
            Response JSON data
            
        Raises:
            Exception: If request fails
        """
        url = f"{NOTION_API_BASE}/{endpoint.lstrip('/')}"
        
        try:
            # Use persistent client with connection pooling
            response = self._http_client.request(
                method=method,
                url=url,
                headers=self.headers,
                json=data
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"Notion API request failed: {e.response.status_code} - {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Notion API request error: {str(e)}")
            raise
    
    def ticket_exists(self, teams_message_id: str) -> bool:
        """
        Check if a ticket with the given Teams Message ID already exists.
        
        Args:
            teams_message_id: Teams message ID to check
            
        Returns:
            True if ticket exists, False otherwise
        """
        try:
            # Query the database for existing ticket with this message ID
            query_data = {
                "filter": {
                    "property": "Teams Message ID",
                    "rich_text": {
                        "equals": teams_message_id
                    }
                }
            }
            
            response = self._make_request("POST", f"/databases/{self.database_id}/query", data=query_data)
            results = response.get("results", [])
            return len(results) > 0
        except Exception as e:
            logger.warning(f"Error checking for existing ticket: {str(e)}")
            # If query fails, assume ticket doesn't exist to avoid blocking creation
            return False
    
    def create_ticket(
        self,
        task_title: str,
        description: str,
        requester_email: str,
        requester_name: Optional[str],
        teams_message_id: str,
        teams_channel: str,
        attachments: List[str],
        approved_by_email: str,
        approved_by_name: Optional[str],
        approved_at: datetime,
        source: Optional[str] = None,
        status: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a new ticket in Notion.
        
        Args:
            task_title: Title of the task
            description: Task description/content
            requester_email: Email of the message author
            requester_name: Name of the message author
            teams_message_id: Unique Teams message ID
            teams_channel: Channel name or ID
            attachments: List of attachment URLs
            approved_by_email: Email of user who added emoji reaction
            approved_by_name: Name of user who added emoji reaction
            approved_at: Timestamp when emoji was added
            source: Source identifier (defaults to config value)
            status: Status value (defaults to config value)
            
        Returns:
            Created page data
            
        Raises:
            Exception: If ticket creation fails
        """
        # Check for duplicates
        if self.ticket_exists(teams_message_id):
            logger.info(f"Ticket with Teams Message ID {teams_message_id} already exists, skipping creation")
            raise ValueError(f"Ticket with Teams Message ID {teams_message_id} already exists")
        
        if source is None:
            source = settings.ticket_source
        if status is None:
            status = settings.default_ticket_status
        
        # Format approved_at timestamp
        approved_at_iso = approved_at.isoformat()
        last_synced_iso = datetime.now(timezone.utc).isoformat()
        
        # Build properties for Notion page
        properties = {
            "Task Title": {
                "title": [
                    {
                        "text": {
                            "content": task_title[:2000]  # Notion title limit
                        }
                    }
                ]
            },
            "Description": {
                "rich_text": [
                    {
                        "text": {
                            "content": description[:2000]  # Truncate if too long
                        }
                    }
                ]
            },
            "Status": {
                "status": {
                    "name": status
                }
            },
            "Requester": self._build_people_property(requester_email),
            "Teams Message ID": {
                "rich_text": [
                    {
                        "text": {
                            "content": teams_message_id
                        }
                    }
                ]
            },
            "Teams Channel": {
                "rich_text": [
                    {
                        "text": {
                            "content": teams_channel
                        }
                    }
                ]
            },
            "Attachments": {
                "url": attachments[0] if attachments else None
            },
            "Approved By": self._build_people_property(approved_by_email),
            "Approved At": {
                "date": {
                    "start": approved_at_iso
                }
            },
            "Source": {
                "rich_text": [
                    {
                        "text": {
                            "content": source
                        }
                    }
                ]
            },
            "Last Synced": {
                "date": {
                    "start": last_synced_iso
                }
            }
        }
        
        page_data = {
            "parent": {
                "database_id": self.database_id
            },
            "properties": properties
        }
        
        logger.info(f"Creating Notion ticket for Teams message {teams_message_id}")
        return self._make_request("POST", "/pages", data=page_data)
