"""Subscription management routes for Microsoft Graph webhooks."""
import logging
from typing import Dict, Any, List
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from services.graph_service import GraphService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/subscription", tags=["subscriptions"])

# Initialize service
graph_service = GraphService()


class CreateSubscriptionRequest(BaseModel):
    """Request model for creating a subscription."""
    resource: str  # e.g., "teams/{teamId}/channels/{channelId}/messages"
    change_types: List[str] = ["created", "updated"]
    expiration_days: float = 3.0  # Can be fractional (e.g., 0.04 for ~1 hour)


class RenewSubscriptionRequest(BaseModel):
    """Request model for renewing a subscription."""
    expiration_days: int = 3


@router.get("/list")
async def list_subscriptions() -> Dict[str, Any]:
    """
    List all active webhook subscriptions.
    
    Returns:
        List of subscriptions
    """
    try:
        subscriptions = graph_service.list_subscriptions()
        return {
            "count": len(subscriptions),
            "subscriptions": subscriptions
        }
    except Exception as e:
        logger.error(f"Error listing subscriptions: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to list subscriptions: {str(e)}")


@router.post("/create")
async def create_subscription(request: CreateSubscriptionRequest) -> Dict[str, Any]:
    """
    Create a new webhook subscription.
    
    Args:
        request: Subscription creation request
        
    Returns:
        Created subscription data
    """
    try:
        from config import settings
        
        # Use timezone-aware datetime to avoid clock skew issues
        now = datetime.now(timezone.utc)
        
        # Calculate expiration - ensure it's at least 30 minutes in the future with buffer
        # Add buffer for local dev (clock skew, network latency, validation delay)
        expiration_datetime = now + timedelta(days=request.expiration_days)
        
        # Microsoft Graph requires expiration to be at least a few minutes in the future
        # Add 30 second buffer for local clock skew and validation latency
        min_expiration = now + timedelta(minutes=30, seconds=30)
        if expiration_datetime < min_expiration:
            expiration_datetime = min_expiration
        
        # Log for debugging
        logger.info(f"Creating subscription for resource: {request.resource}")
        logger.info(f"Local UTC NOW: {now.isoformat()}")
        logger.info(f"SUB EXPIRATION: {expiration_datetime.isoformat()}")
        logger.info(f"Expiration in minutes: {(expiration_datetime - now).total_seconds() / 60:.1f}")
        
        # Validate webhook URL configuration
        if not settings.webhook_notification_url:
            raise ValueError("WEBHOOK_NOTIFICATION_URL not configured in .env file")
        
        if not settings.webhook_client_state:
            raise ValueError("WEBHOOK_CLIENT_STATE not configured in .env file")
        
        # Determine lifecycle notification URL
        # For Teams messages, lifecycleNotificationUrl is REQUIRED (enforced by guard function)
        # For other resources, include it if expiration > 1 hour
        base_url = settings.webhook_notification_url.rsplit("/webhook/notification", 1)[0]
        lifecycle_url = f"{base_url}/webhook/lifecycle"
        
        # Detect Teams messages - must match guard function logic
        # Check both with and without leading slash, and ensure "/messages" is in the path
        resource_normalized = request.resource if request.resource.startswith("/") else f"/{request.resource}"
        is_teams_message = resource_normalized.startswith("/teams/") and "/messages" in resource_normalized
        
        if is_teams_message:
            # Teams messages ALWAYS require lifecycleNotificationUrl
            lifecycle_notification_url = lifecycle_url
            logger.info(f"Teams message detected - lifecycleNotificationUrl will be included")
        elif expiration_datetime > now + timedelta(hours=1):
            # Other resources only need it if expiration > 1 hour
            lifecycle_notification_url = lifecycle_url
        else:
            lifecycle_notification_url = None
        
        # Log webhook URLs for debugging
        logger.info(f"Notification URL: {settings.webhook_notification_url}")
        logger.info(f"Lifecycle URL: {lifecycle_notification_url if lifecycle_notification_url else 'N/A'}")
        
        # All normalization (changeType filtering, expiration capping, resource formatting)
        # is now handled by the guard function in GraphService.create_subscription()
        subscription = graph_service.create_subscription(
            resource=request.resource,
            change_types=request.change_types,  # Guard function will filter if needed
            notification_url=settings.webhook_notification_url,
            expiration_datetime=expiration_datetime,
            lifecycle_notification_url=lifecycle_notification_url
        )
        
        logger.info(f"Successfully created subscription {subscription.get('id')} for resource {request.resource}")
        return subscription
    except ValueError as e:
        # Configuration or validation errors
        logger.error(f"Configuration error creating subscription: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Configuration error: {str(e)}")
    except Exception as e:
        # Other errors
        logger.error(f"Error creating subscription: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to create subscription: {str(e)}")


@router.post("/renew/{subscription_id}")
async def renew_subscription(
    subscription_id: str,
    request: RenewSubscriptionRequest
) -> Dict[str, Any]:
    """
    Renew a webhook subscription by extending its expiration.
    
    Args:
        subscription_id: ID of the subscription to renew
        request: Renewal request with expiration days
        
    Returns:
        Updated subscription data
    """
    try:
        expiration_datetime = datetime.now(timezone.utc) + timedelta(days=request.expiration_days)
        
        subscription = graph_service.renew_subscription(
            subscription_id=subscription_id,
            expiration_datetime=expiration_datetime
        )
        
        logger.info(f"Renewed subscription {subscription_id}")
        return subscription
    except Exception as e:
        logger.error(f"Error renewing subscription: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to renew subscription: {str(e)}")


@router.delete("/delete/{subscription_id}")
async def delete_subscription(subscription_id: str) -> Dict[str, str]:
    """
    Delete a webhook subscription.
    
    Args:
        subscription_id: ID of the subscription to delete
        
    Returns:
        Success message
    """
    try:
        graph_service.delete_subscription(subscription_id)
        logger.info(f"Deleted subscription {subscription_id}")
        return {"status": "success", "message": f"Subscription {subscription_id} deleted"}
    except Exception as e:
        logger.error(f"Error deleting subscription: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to delete subscription: {str(e)}")


@router.post("/renew-all")
async def renew_all_subscriptions(request: RenewSubscriptionRequest) -> Dict[str, Any]:
    """
    Renew all active subscriptions.
    
    Args:
        request: Renewal request with expiration days
        
    Returns:
        Summary of renewal operations
    """
    try:
        subscriptions = graph_service.list_subscriptions()
        renewed = []
        failed = []
        
        expiration_datetime = datetime.now(timezone.utc) + timedelta(days=request.expiration_days)
        
        for sub in subscriptions:
            sub_id = sub.get("id")
            if sub_id:
                try:
                    graph_service.renew_subscription(sub_id, expiration_datetime)
                    renewed.append(sub_id)
                except Exception as e:
                    logger.error(f"Failed to renew subscription {sub_id}: {str(e)}")
                    failed.append({"id": sub_id, "error": str(e)})
        
        return {
            "total": len(subscriptions),
            "renewed": len(renewed),
            "failed": len(failed),
            "renewed_ids": renewed,
            "failed_ids": failed
        }
    except Exception as e:
        logger.error(f"Error renewing all subscriptions: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to renew subscriptions: {str(e)}")
