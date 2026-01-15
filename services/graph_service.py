"""Microsoft Graph API service for Teams integration."""
import logging
import time
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta, timezone
import httpx
from msal import ConfidentialClientApplication
from config import settings
from models.webhook_models import GraphMessage
from utils.graph_subscriptions import normalize_graph_subscription

logger = logging.getLogger(__name__)

# Microsoft Graph API endpoints
GRAPH_API_BASE = "https://graph.microsoft.com/v1.0"
GRAPH_AUTHORITY = f"https://login.microsoftonline.com/{settings.microsoft_tenant_id}"

# Connection pool settings for better performance
CONNECTION_LIMIT = 10
TIMEOUT = 30.0


class GraphService:
    """Service for interacting with Microsoft Graph API."""
    
    def __init__(self):
        """Initialize the Graph service with MSAL app and connection pooling."""
        self.app = ConfidentialClientApplication(
            client_id=settings.microsoft_client_id,
            client_credential=settings.microsoft_client_secret,
            authority=GRAPH_AUTHORITY
        )
        self._access_token: Optional[str] = None
        self._token_expires_at: Optional[datetime] = None
        
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
        
        logger.info(f"GraphService initialized with connection pooling (max={CONNECTION_LIMIT})")
    
    def __del__(self):
        """Cleanup httpx client on destruction."""
        if hasattr(self, '_http_client'):
            self._http_client.close()
            logger.debug("GraphService httpx client closed")
    
    def _get_access_token(self) -> str:
        """
        Get a valid access token, refreshing if necessary.
        
        Returns:
            Access token string
            
        Raises:
            Exception: If token acquisition fails
        """
        # Check if we have a valid token
        if self._access_token and self._token_expires_at:
            if datetime.now(timezone.utc) < self._token_expires_at - timedelta(minutes=5):
                return self._access_token
        
        # Acquire new token
        result = self.app.acquire_token_for_client(
            scopes=["https://graph.microsoft.com/.default"]
        )
        
        if "access_token" not in result:
            error = result.get("error_description", "Unknown error")
            raise Exception(f"Failed to acquire access token: {error}")
        
        self._access_token = result["access_token"]
        expires_in = result.get("expires_in", 3600)
        self._token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
        
        return self._access_token
    
    def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Make an authenticated request to Microsoft Graph API.
        
        Uses persistent httpx client with connection pooling for better performance.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint (relative to base URL)
            data: Request body data
            params: Query parameters
            
        Returns:
            Response JSON data
            
        Raises:
            Exception: If request fails
        """
        token = self._get_access_token()
        url = f"{GRAPH_API_BASE}/{endpoint.lstrip('/')}"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        try:
            # Log request details for debugging (excluding sensitive data)
            if data:
                log_data = {k: v for k, v in data.items() if k != "clientState"}
                logger.debug(f"Graph API request: {method} {url} with data: {log_data}")
            
            # Use persistent client with connection pooling
            response = self._http_client.request(
                method=method,
                url=url,
                headers=headers,
                json=data,
                params=params
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            error_detail = e.response.text
            error_code = "Unknown"
            is_validation_timeout = False
            
            try:
                error_json = e.response.json()
                error_detail = error_json.get("error", {}).get("message", error_detail)
                error_code = error_json.get("error", {}).get("code", "Unknown")
                
                # Extract request-id for latency tracking
                request_id = error_json.get("error", {}).get("innerError", {}).get("request-id")
                
                # Check if this is a validation timeout error
                is_validation_timeout = (
                    error_code == "ValidationError" and 
                    "timeout" in error_detail.lower()
                ) or "Subscription validation request timed out" in error_detail
                
                # Log full error response for debugging
                logger.error(f"Graph API full error response: {error_json}")
                logger.error(f"Graph API error code: {error_code}")
                if request_id:
                    logger.error(f"Graph API request-id: {request_id}")
                
                # Special logging for validation timeout
                if is_validation_timeout:
                    logger.error(
                        "VALIDATION TIMEOUT DETECTED: Microsoft Graph validation request timed out. "
                        "This usually indicates the service was cold or network latency delayed the validation request. "
                        "The webhook endpoint may have responded correctly, but too late for Microsoft Graph's timeout window."
                    )
                    # Store request-id for latency tracking (will be matched when validation arrives)
                    if request_id and hasattr(self, '_last_subscription_resource'):
                        from routes.webhooks import _subscription_creation_times
                        import time
                        _subscription_creation_times[request_id] = (
                            time.time(),
                            getattr(self, '_last_subscription_resource', 'unknown')
                        )
            except:
                pass
            
            logger.error(f"Graph API request failed: {e.response.status_code} - {error_detail}")
            logger.error(f"Request URL: {url}")
            logger.error(f"Request method: {method}")
            
            # Preserve validation timeout information in exception message
            if is_validation_timeout:
                raise Exception(f"Graph API error {e.response.status_code}: Subscription validation request timed out.")
            else:
                raise Exception(f"Graph API error {e.response.status_code}: {error_detail}")
        except Exception as e:
            logger.error(f"Graph API request error: {str(e)}")
            raise
    
    def create_subscription(
        self,
        resource: str,
        change_types: List[str],
        notification_url: str,
        expiration_datetime: Optional[datetime] = None,
        lifecycle_notification_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a webhook subscription.
        
        Uses normalize_graph_subscription to enforce all Microsoft Graph rules
        and prevent validation errors.
        
        Args:
            resource: Resource to subscribe to (e.g., "teams/{teamId}/channels/{channelId}/messages")
            change_types: List of change types (e.g., ["created", "updated"])
            notification_url: URL to receive notifications
            expiration_datetime: Subscription expiration (default: 1 hour for Teams, 3 days for others)
            lifecycle_notification_url: URL for lifecycle notifications (required for Teams subscriptions)
            
        Returns:
            Subscription data
        """
        # Use centralized normalization function
        subscription_data = normalize_graph_subscription(
            resource=resource,
            change_types=change_types,
            notification_url=notification_url,
            lifecycle_notification_url=lifecycle_notification_url,
            expiration_datetime=expiration_datetime,
            client_state=settings.webhook_client_state,
        )
        
        # Store resource for latency tracking
        self._last_subscription_resource = resource
        self._last_subscription_creation_time = time.time()
        
        # Log the subscription payload for debugging
        logger.info(f"Creating subscription with payload: {subscription_data}")
        
        try:
            result = self._make_request("POST", "/subscriptions", data=subscription_data)
            # If successful, we can't track latency (no request-id in success response)
            return result
        except Exception as e:
            # Error handling in _make_request will store request-id if available
            raise
    
    def create_subscription_with_retry(
        self,
        resource: str,
        change_types: List[str],
        notification_url: str,
        expiration_datetime: Optional[datetime] = None,
        lifecycle_notification_url: Optional[str] = None,
        max_retries: int = 5,
        initial_delay: float = 1.0
    ) -> Dict[str, Any]:
        """
        Create a webhook subscription with automatic retry on validation timeout.
        
        Retries subscription creation with exponential backoff if Microsoft Graph
        validation request times out. This handles cases where the service is cold
        or network latency delays validation requests.
        
        Args:
            resource: Resource to subscribe to
            change_types: List of change types
            notification_url: URL to receive notifications
            expiration_datetime: Subscription expiration
            lifecycle_notification_url: URL for lifecycle notifications
            max_retries: Maximum number of retry attempts (default: 3)
            initial_delay: Initial delay in seconds before first retry (default: 2.0)
            
        Returns:
            Subscription data
            
        Raises:
            Exception: If all retries fail
        """
        import time
        
        last_exception = None
        
        for attempt in range(max_retries):
            try:
                # Before retry (except first attempt), ensure service is warm
                if attempt > 0:
                    # Use variable delay strategy: shorter delays for rapid retry mode, exponential for normal
                    if initial_delay < 1.0:
                        # Rapid retry mode: shorter, more frequent attempts
                        delay = initial_delay * (1.5 ** (attempt - 1))
                        delay = min(delay, 2.0)  # Cap at 2 seconds for rapid mode
                    else:
                        # Normal mode: exponential backoff
                        delay = initial_delay * (2 ** (attempt - 1))
                        delay = min(delay, 10.0)  # Cap at 10 seconds for normal mode
                    
                    logger.info(f"Retry attempt {attempt + 1}/{max_retries} after {delay:.2f}s delay")
                    time.sleep(delay)
                    
                    # Ensure token is fresh before retry (skip for very short delays in rapid mode)
                    if delay >= 1.0:
                        logger.info("Refreshing access token before retry...")
                        try:
                            self._get_access_token()
                            logger.info("Token refreshed successfully")
                        except Exception as e:
                            logger.warning(f"Token refresh failed: {str(e)}, will continue anyway")
                    else:
                        # For rapid retry, just check if token exists
                        if not self._access_token:
                            try:
                                self._get_access_token()
                            except:
                                pass
                
                # Attempt to create subscription
                return self.create_subscription(
                    resource=resource,
                    change_types=change_types,
                    notification_url=notification_url,
                    expiration_datetime=expiration_datetime,
                    lifecycle_notification_url=lifecycle_notification_url
                )
                
            except Exception as e:
                last_exception = e
                error_message = str(e)
                
                # Check if this is a validation timeout error
                is_validation_timeout = (
                    "Subscription validation request timed out" in error_message or
                    ("ValidationError" in error_message and "timeout" in error_message.lower())
                )
                
                if is_validation_timeout and attempt < max_retries - 1:
                    logger.warning(
                        f"Subscription validation timeout on attempt {attempt + 1}/{max_retries}. "
                        f"Error: {error_message}. Will retry..."
                    )
                    continue
                else:
                    # Not a validation timeout, or out of retries
                    if attempt < max_retries - 1:
                        logger.warning(
                            f"Subscription creation failed on attempt {attempt + 1}/{max_retries}. "
                            f"Error: {error_message}. Will retry..."
                        )
                    else:
                        logger.error(
                            f"Subscription creation failed after {max_retries} attempts. "
                            f"Last error: {error_message}"
                        )
                    raise
        
        # Should never reach here, but just in case
        if last_exception:
            raise last_exception
        raise Exception("Subscription creation failed after all retries")
    
    def list_subscriptions(self) -> List[Dict[str, Any]]:
        """
        List all active subscriptions.
        
        Returns:
            List of subscription data
        """
        response = self._make_request("GET", "/subscriptions")
        return response.get("value", [])
    
    def renew_subscription(self, subscription_id: str, expiration_datetime: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Renew a subscription by updating its expiration.
        
        Args:
            subscription_id: ID of the subscription to renew
            expiration_datetime: New expiration (default: 3 days from now)
            
        Returns:
            Updated subscription data
        """
        if expiration_datetime is None:
            expiration_datetime = datetime.now(timezone.utc) + timedelta(days=3)
        
        # Format datetime for Microsoft Graph (must end with Z, not +00:00)
        expiration_str = expiration_datetime.isoformat()
        if expiration_str.endswith('+00:00'):
            expiration_str = expiration_str.replace('+00:00', 'Z')
        elif not expiration_str.endswith('Z'):
            expiration_str = expiration_str + 'Z'
        
        update_data = {
            "expirationDateTime": expiration_str
        }
        
        return self._make_request("PATCH", f"/subscriptions/{subscription_id}", data=update_data)
    
    def delete_subscription(self, subscription_id: str) -> None:
        """
        Delete a subscription.
        
        Args:
            subscription_id: ID of the subscription to delete
        """
        self._make_request("DELETE", f"/subscriptions/{subscription_id}")
    
    def get_message(self, team_id: str, channel_id: str, message_id: str) -> GraphMessage:
        """
        Get a Teams channel message with full details including reactions.
        
        Args:
            team_id: Team ID
            channel_id: Channel ID
            message_id: Message ID
            
        Returns:
            Message object with reactions
        """
        endpoint = f"/teams/{team_id}/channels/{channel_id}/messages/{message_id}"
        # Expand reactions to get full details
        params = {"$expand": "reactions"}
        
        data = self._make_request("GET", endpoint, params=params)
        return GraphMessage(**data)
    
    def get_channel_info(self, team_id: str, channel_id: str) -> Dict[str, Any]:
        """
        Get channel information.
        
        Args:
            team_id: Team ID
            channel_id: Channel ID
            
        Returns:
            Channel data
        """
        endpoint = f"/teams/{team_id}/channels/{channel_id}"
        return self._make_request("GET", endpoint)
    
    def get_user_info(self, user_id: str) -> Dict[str, Any]:
        """
        Get user information.
        
        Args:
            user_id: User ID or principal name
            
        Returns:
            User data
        """
        endpoint = f"/users/{user_id}"
        return self._make_request("GET", endpoint)
