"""Webhook routes for Microsoft Graph notifications."""
import logging
import time
from typing import Dict, Any, Optional, Tuple
from fastapi import APIRouter, Request, Response, HTTPException
from fastapi.responses import PlainTextResponse
from models.webhook_models import Notification, ChangeNotification
from services.graph_service import GraphService
from services.notion_service import NotionService
from utils.validation import is_user_allowed
from utils.auth import verify_webhook_client_state
from datetime import datetime, timezone
from urllib.parse import unquote
import re
from collections import defaultdict

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhook", tags=["webhooks"])

# Initialize services
graph_service = GraphService()
notion_service = NotionService()

# Track subscription creation times for latency analysis
# Key: request_id from validation token, Value: (subscription_creation_time, resource)
_subscription_creation_times: Dict[str, Tuple[float, str]] = {}

# Ticket emoji to look for
TICKET_EMOJI = "🎫"


@router.api_route("", methods=["GET", "POST"])
async def webhook_root(request: Request):
    """
    Root webhook endpoint for Microsoft Graph validation.
    
    Microsoft Graph may validate at /webhook instead of /webhook/notification.
    This endpoint catches those validation requests and responds immediately.
    
    CRITICAL: Must respond in < 2 seconds to avoid validation timeout.
    Optimized for fastest possible response - no logging, no processing.
    """
    # Check for validation token in query string (fastest method)
    query_string = request.url.query
    if query_string and "validationToken=" in query_string:
        # Extract token directly (no URL decode needed - Graph accepts encoded)
        token_start = query_string.find("validationToken=") + len("validationToken=")
        token_end = query_string.find("&", token_start)
        if token_end == -1:
            token_end = len(query_string)
        
        validation_token = query_string[token_start:token_end]
        
        # Return immediately - no processing, no logging overhead
        return PlainTextResponse(content=validation_token, status_code=200)
    
    # Fallback to query_params
    validation_token = request.query_params.get("validationToken")
    if validation_token:
        return PlainTextResponse(content=validation_token, status_code=200)
    
    # If no validation token, return 404 (not a valid endpoint for notifications)
    raise HTTPException(status_code=404, detail="Use /webhook/notification or /webhook/lifecycle for notifications")


def extract_team_channel_from_resource(resource: str) -> Optional[Tuple[str, str, str]]:
    """
    Extract team ID and channel ID from resource URL.
    
    Args:
        resource: Resource URL from webhook notification
        
    Returns:
        Tuple of (team_id, channel_id) or None if parsing fails
    """
    # Resource format: /teams/{teamId}/channels/{channelId}/messages/{messageId}
    pattern = r"/teams/([^/]+)/channels/([^/]+)/messages/([^/]+)"
    match = re.search(pattern, resource)
    if match:
        return match.group(1), match.group(2), match.group(3)
    return None


async def process_message_reaction(notification: ChangeNotification) -> None:
    """
    Process a message reaction notification.
    
    Args:
        notification: Change notification from webhook
    """
    try:
        # Extract team, channel, and message IDs from resource
        resource_info = extract_team_channel_from_resource(notification.resource)
        if not resource_info:
            logger.warning(f"Could not parse resource: {notification.resource}")
            return
        
        team_id, channel_id, message_id = resource_info
        
        # Fetch full message details including reactions
        logger.info(f"Fetching message {message_id} from team {team_id}, channel {channel_id}")
        message = graph_service.get_message(team_id, channel_id, message_id)
        
        # Check if ticket emoji reaction exists
        ticket_reaction = None
        if message.reactions:
            for reaction in message.reactions:
                if reaction.reactionType == TICKET_EMOJI:
                    ticket_reaction = reaction
                    break
        
        if not ticket_reaction:
            logger.debug(f"No ticket emoji reaction found on message {message_id}")
            return
        
        # Get user who added the reaction
        reacting_user = ticket_reaction.user
        reacting_user_email = reacting_user.get("userIdentity", {}).get("id") or \
                             reacting_user.get("id")
        
        # Check if user is allowed
        if not is_user_allowed(reacting_user_email):
            logger.info(f"User {reacting_user_email} is not allowed to create tickets")
            return
        
        # Get user details for approved_by
        try:
            user_info = graph_service.get_user_info(reacting_user_email)
            approved_by_name = user_info.get("displayName")
            approved_by_email = user_info.get("mail") or user_info.get("userPrincipalName") or reacting_user_email
        except Exception as e:
            logger.warning(f"Could not fetch user info for {reacting_user_email}: {str(e)}")
            approved_by_name = None
            approved_by_email = reacting_user_email
        
        # Get message author details
        requester_email = None
        requester_name = None
        if message.from_ and message.from_.user:
            requester_id = message.from_.user.get("id")
            if requester_id:
                try:
                    requester_info = graph_service.get_user_info(requester_id)
                    requester_name = requester_info.get("displayName")
                    requester_email = requester_info.get("mail") or requester_info.get("userPrincipalName") or requester_id
                except Exception as e:
                    logger.warning(f"Could not fetch requester info: {str(e)}")
                    requester_email = requester_id
        
        if not requester_email:
            logger.warning(f"Could not determine requester for message {message_id}")
            requester_email = "Unknown"
        
        # Get channel info
        try:
            channel_info = graph_service.get_channel_info(team_id, channel_id)
            channel_name = channel_info.get("displayName", channel_id)
        except Exception as e:
            logger.warning(f"Could not fetch channel info: {str(e)}")
            channel_name = channel_id
        
        # Extract message content
        message_body = ""
        if message.body:
            message_body = message.body.content or ""
            # Strip HTML tags for cleaner text (basic)
            message_body = re.sub(r'<[^>]+>', '', message_body)
        
        # Extract task title from subject or first line of message
        task_title = message.subject or "Teams Ticket"
        if not message.subject and message_body:
            # Use first line or first 100 chars as title
            first_line = message_body.split('\n')[0].strip()
            task_title = first_line[:100] if first_line else "Teams Ticket"
        
        # Get attachments
        attachments = []
        if message.attachments:
            for attachment in message.attachments:
                if attachment.contentUrl:
                    attachments.append(attachment.contentUrl)
        
        # Get reaction timestamp (use message last modified or current time)
        approved_at = message.lastModifiedDateTime or datetime.now(timezone.utc)
        if isinstance(approved_at, str):
            # Parse ISO format string
            try:
                approved_at = datetime.fromisoformat(approved_at.replace('Z', '+00:00'))
            except:
                approved_at = datetime.now(timezone.utc)
        
        # Create ticket in Notion
        logger.info(f"Creating Notion ticket for message {message_id}")
        notion_service.create_ticket(
            task_title=task_title,
            description=message_body,
            requester_email=requester_email,
            requester_name=requester_name,
            teams_message_id=message_id,
            teams_channel=channel_name,
            attachments=attachments,
            approved_by_email=approved_by_email,
            approved_by_name=approved_by_name,
            approved_at=approved_at,
        )
        
        logger.info(f"Successfully created Notion ticket for message {message_id}")
        
    except ValueError as e:
        # Duplicate ticket - this is expected, just log
        logger.info(f"Ticket already exists: {str(e)}")
    except Exception as e:
        logger.error(f"Error processing message reaction: {str(e)}", exc_info=True)
        raise


@router.get("/validation")
def webhook_validation(validationToken: Optional[str] = None):
    """
    Handle webhook validation request from Microsoft Graph (GET method).
    Note: Microsoft Graph primarily uses POST with validationToken in query params,
    but this endpoint is kept for compatibility.
    
    CRITICAL: Must respond in < 2 seconds to avoid validation timeout.
    
    Args:
        validationToken: Validation token sent by Microsoft Graph
        
    Returns:
        Validation token as plain text
    """
    start_time = time.perf_counter()
    
    if validationToken:
        # Calculate response time in milliseconds
        response_time_ms = (time.perf_counter() - start_time) * 1000
        logger.info(f"GET /webhook/validation - Validation request received, response time: {response_time_ms:.2f}ms")
        
        # Warn if response time is slow
        if response_time_ms > 100:
            logger.warning(f"GET /webhook/validation - Slow response time: {response_time_ms:.2f}ms (should be < 100ms)")
        
        return PlainTextResponse(content=validationToken, status_code=200)
    else:
        raise HTTPException(status_code=400, detail="Missing validationToken")


@router.get("/lifecycle/validation")
def webhook_lifecycle_validation(validationToken: Optional[str] = None) -> Response:
    """
    Handle webhook validation request for lifecycle notifications from Microsoft Graph.
    Microsoft Graph validates both notificationUrl and lifecycleNotificationUrl.
    
    CRITICAL: Must respond in < 2 seconds to avoid validation timeout.
    
    Args:
        validationToken: Validation token sent by Microsoft Graph
        
    Returns:
        Validation token as plain text
    """
    start_time = time.perf_counter()
    
    if validationToken:
        # Calculate response time in milliseconds
        response_time_ms = (time.perf_counter() - start_time) * 1000
        logger.info(f"GET /webhook/lifecycle/validation - Validation request received, response time: {response_time_ms:.2f}ms")
        
        # Warn if response time is slow
        if response_time_ms > 100:
            logger.warning(f"GET /webhook/lifecycle/validation - Slow response time: {response_time_ms:.2f}ms (should be < 100ms)")
        
        return PlainTextResponse(content=validationToken, status_code=200)
    else:
        raise HTTPException(status_code=400, detail="Missing validationToken")


@router.post("/lifecycle", response_model=None)
async def webhook_lifecycle(request: Request):
    """
    Handle webhook lifecycle notifications from Microsoft Graph.
    Also handles validation requests sent as POST with validationToken query param.
    Optimized for fastest possible validation response.
    
    CRITICAL: Must respond in < 2 seconds to avoid validation timeout.
    
    Returns:
        Success response or validation token
    """
    # CRITICAL: Check validation token FIRST using fastest method possible
    # Access query string directly without converting entire URL to string
    start_time = time.perf_counter()
    query_string = request.url.query
    if query_string and "validationToken=" in query_string:
        # Extract token from query string directly (fastest method, no async operations)
        token_start = query_string.find("validationToken=") + len("validationToken=")
        token_end = query_string.find("&", token_start)
        if token_end == -1:
            token_end = len(query_string)
        
        validation_token = query_string[token_start:token_end]
        # URL decode the token
        validation_token = unquote(validation_token)
        
        # Calculate and log response time
        response_time_ms = (time.perf_counter() - start_time) * 1000
        logger.info(f"POST /webhook/lifecycle - Validation request received, response time: {response_time_ms:.2f}ms")
        
        # Warn if response time is slow
        if response_time_ms > 100:
            logger.warning(f"POST /webhook/lifecycle - Slow validation response time: {response_time_ms:.2f}ms (should be < 100ms)")
        
        # Return immediately - NO async operations, NO body reading, NO processing
        # Microsoft Graph requires response in < 2 seconds
        return PlainTextResponse(content=validation_token, status_code=200)
    
    # Fallback to query_params if query string parsing didn't find it (shouldn't happen, but safe)
    validation_token = request.query_params.get("validationToken")
    if validation_token:
        # Calculate and log response time
        response_time_ms = (time.perf_counter() - start_time) * 1000
        logger.info(f"POST /webhook/lifecycle (fallback) - Validation request received, response time: {response_time_ms:.2f}ms")
        
        return PlainTextResponse(content=validation_token, status_code=200)
    
    # Otherwise, parse as notification
    try:
        body = await request.body()
        if not body:
            # CRITICAL: Microsoft Graph sometimes sends empty POSTs during reachability checks
            # NEVER return 4xx here - Graph treats ANY 4xx as validation failure
            return PlainTextResponse("OK", status_code=202)
        
        notification_data = await request.json()
        notification = Notification(**notification_data)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to parse lifecycle notification: {str(e)}")
        # Even for parsing errors, return 202 to avoid Graph blacklisting
        return PlainTextResponse("OK", status_code=202)
    
    logger.info(f"Received lifecycle notification with {len(notification.value)} change(s)")
    
    # Process lifecycle events (subscription expiration, etc.)
    for change in notification.value:
        try:
            logger.info(f"Lifecycle event: {change.changeType} for subscription {change.subscriptionId}")
            
            # Handle subscription expiration warnings
            if change.changeType == "subscriptionRemoved" or "expired" in change.changeType.lower():
                logger.warning(f"Subscription {change.subscriptionId} has expired or been removed")
                # You could implement auto-renewal here if needed
                
        except Exception as e:
            logger.error(f"Error processing lifecycle notification: {str(e)}", exc_info=True)
    
    return PlainTextResponse("OK", status_code=202)


@router.post("/notification", response_model=None)
async def webhook_notification(request: Request):
    """
    Handle webhook notification from Microsoft Graph.
    Also handles validation requests sent as POST with validationToken query param.
    Optimized for fastest possible validation response.
    
    CRITICAL: Must respond in < 2 seconds to avoid validation timeout.
    
    Returns:
        Success response or validation token
    """
    # CRITICAL: Check validation token FIRST using fastest method possible
    # Access query string directly without converting entire URL to string
    # This must happen BEFORE any async operations (body reading, etc.)
    start_time = time.perf_counter()
    validation_arrival_time = time.time()
    query_string = request.url.query
    if query_string and "validationToken=" in query_string:
        # Extract token from query string directly (fastest method, no async operations)
        token_start = query_string.find("validationToken=") + len("validationToken=")
        token_end = query_string.find("&", token_start)
        if token_end == -1:
            token_end = len(query_string)
        
        validation_token = unquote(query_string[token_start:token_end])
        
        # Extract request-id from validation token for latency tracking
        # Format: "Validation: Testing client application reachability for subscription Request-Id: {request-id}"
        request_id = None
        if "Request-Id:" in validation_token:
            try:
                request_id = validation_token.split("Request-Id:")[-1].strip().lstrip('+')
            except:
                pass
        
        # Calculate and log response time
        response_time_ms = (time.perf_counter() - start_time) * 1000
        logger.info(f"POST /webhook/notification - Validation request received, response time: {response_time_ms:.2f}ms")
        
        # Track network latency if we have request-id and subscription creation time
        if request_id and request_id in _subscription_creation_times:
            creation_time, resource = _subscription_creation_times[request_id]
            network_latency = validation_arrival_time - creation_time
            network_latency_ms = network_latency * 1000
            logger.warning(
                f"NETWORK LATENCY DETECTED: Validation request arrived {network_latency_ms:.2f}ms "
                f"({network_latency:.2f}s) after subscription creation for resource: {resource}. "
                f"Request-ID: {request_id}"
            )
            # Clean up old entry
            del _subscription_creation_times[request_id]
        elif request_id:
            logger.info(f"Validation request received with Request-ID: {request_id} (no matching subscription creation found)")
        
        # Warn if response time is slow
        if response_time_ms > 100:
            logger.warning(f"POST /webhook/notification - Slow validation response time: {response_time_ms:.2f}ms (should be < 100ms)")
        
        # Return immediately - NO async operations, NO body reading, NO processing
        # Microsoft Graph requires response in < 2 seconds
        return PlainTextResponse(content=validation_token, status_code=200)
    
    # Fallback to query_params if query string parsing didn't find it (shouldn't happen, but safe)
    validation_token = request.query_params.get("validationToken")
    if validation_token:
        # Calculate and log response time
        response_time_ms = (time.perf_counter() - start_time) * 1000
        logger.info(f"POST /webhook/notification (fallback) - Validation request received, response time: {response_time_ms:.2f}ms")
        
        return PlainTextResponse(content=validation_token, status_code=200)
    
    # Otherwise, parse as notification
    try:
        body = await request.body()
        if not body:
            # CRITICAL: Microsoft Graph sometimes sends empty POSTs during reachability checks
            # NEVER return 4xx here - Graph treats ANY 4xx as validation failure
            # Return 202 Accepted to indicate we received the request
            return PlainTextResponse("OK", status_code=202)
        
        notification_data = await request.json()
        notification = Notification(**notification_data)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to parse notification: {str(e)}")
        # Even for parsing errors, return 202 to avoid Graph blacklisting
        return PlainTextResponse("OK", status_code=202)
    
    logger.info(f"Received webhook notification with {len(notification.value)} change(s)")
    
    # Process validation tokens if present
    if notification.validationTokens:
        logger.debug("Validation tokens in notification (already validated)")
    
    # Process each change notification
    for change in notification.value:
        try:
            # Verify client state
            if change.clientState and not verify_webhook_client_state(change.clientState):
                logger.warning(f"Invalid client state in notification: {change.clientState}")
                continue
            
            # Check if this is a message-related change
            if "/messages" in change.resource:
                if change.changeType in ["created", "updated"]:
                    # Process message reaction
                    await process_message_reaction(change)
                else:
                    logger.debug(f"Ignoring change type: {change.changeType}")
            else:
                logger.debug(f"Ignoring non-message resource: {change.resource}")
                
        except Exception as e:
            logger.error(f"Error processing change notification: {str(e)}", exc_info=True)
            # Continue processing other notifications even if one fails
    
    # Return 202 Accepted to acknowledge receipt
    return PlainTextResponse("OK", status_code=202)
