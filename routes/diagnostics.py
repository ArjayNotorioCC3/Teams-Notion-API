"""Diagnostics and testing endpoints for local development."""
import logging
from typing import Dict, Any
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from services.graph_service import GraphService
from services.notion_service import NotionService
from config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/diagnostics", tags=["diagnostics"])

# Initialize services
graph_service = GraphService()
notion_service = NotionService()


class TestWebhookRequest(BaseModel):
    """Request model for testing webhook validation."""
    test_url: str  # URL to test
    validation_token: str = "test_token_12345"


class WebhookTestResult(BaseModel):
    """Result of webhook test."""
    url: str
    success: bool
    response_time_ms: float
    error: str = None
    status_code: int = None


@router.get("/config")
async def get_config() -> Dict[str, Any]:
    """
    Get current configuration (sensitive values masked).
    
    Returns:
        Configuration overview
    """
    return {
        "microsoft_client_id": settings.microsoft_client_id[:8] + "..." if settings.microsoft_client_id else None,
        "microsoft_tenant_id": settings.microsoft_tenant_id,
        "notion_database_id": settings.notion_database_id[:8] + "..." if settings.notion_database_id else None,
        "webhook_notification_url": settings.webhook_notification_url,
        "allowed_users_count": len(settings.allowed_users),
        "default_ticket_status": settings.default_ticket_status,
        "ticket_source": settings.ticket_source,
        "current_utc_time": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/health")
async def health_check() -> Dict[str, Any]:
    """
    Comprehensive health check.
    
    Returns:
        Health status of all components
    """
    health = {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "components": {}
    }
    
    # Check Graph API connection
    try:
        graph_service._get_access_token()
        health["components"]["graph_api"] = {
            "status": "connected",
            "token_valid": True
        }
    except Exception as e:
        health["components"]["graph_api"] = {
            "status": "disconnected",
            "error": str(e)
        }
        health["status"] = "unhealthy"
    
    # Check Notion API connection
    try:
        # Try to query the database
        notion_service._make_request("GET", f"/databases/{notion_service.database_id}")
        health["components"]["notion_api"] = {
            "status": "connected",
            "database_accessible": True
        }
    except Exception as e:
        health["components"]["notion_api"] = {
            "status": "disconnected",
            "error": str(e)
        }
        health["status"] = "unhealthy"
    
    # Check configuration
    try:
        if not settings.webhook_notification_url:
            raise ValueError("Missing webhook_notification_url")
        if not settings.webhook_client_state:
            raise ValueError("Missing webhook_client_state")
        if not settings.allowed_users:
            raise ValueError("Missing allowed_users")
        
        health["components"]["configuration"] = {
            "status": "valid",
            "webhook_url": settings.webhook_notification_url,
            "client_state_configured": True
        }
    except Exception as e:
        health["components"]["configuration"] = {
            "status": "invalid",
            "error": str(e)
        }
        health["status"] = "unhealthy"
    
    return health


@router.post("/test-subscription-payload")
async def test_subscription_payload(resource: str) -> Dict[str, Any]:
    """
    Test subscription payload generation without actually creating subscription.
    
    Args:
        resource: Resource path to subscribe to (e.g., "teams/{teamId}/channels/{channelId}/messages")
        
    Returns:
        Generated subscription payload for inspection
    """
    try:
        from utils.graph_subscriptions import normalize_graph_subscription
        from datetime import timedelta
        
        # Test payload generation
        now = datetime.now(timezone.utc)
        expiration_datetime = now + timedelta(hours=1)
        
        # Determine lifecycle URL
        base_url = settings.webhook_notification_url.rsplit("/webhook/notification", 1)[0]
        lifecycle_url = f"{base_url}/webhook/lifecycle"
        
        subscription_data = normalize_graph_subscription(
            resource=resource,
            change_types=["created", "updated"],
            notification_url=settings.webhook_notification_url,
            lifecycle_notification_url=lifecycle_url,
            expiration_datetime=expiration_datetime,
            client_state=settings.webhook_client_state,
        )
        
        return {
            "success": True,
            "payload": subscription_data,
            "resource_type": "teams_messages" if "/teams/" in resource and "/messages" in resource else "other",
            "current_utc": now.isoformat(),
            "expiration_utc": expiration_datetime.isoformat(),
        }
    except Exception as e:
        logger.error(f"Error testing subscription payload: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }


@router.get("/subscriptions")
async def list_all_subscriptions() -> Dict[str, Any]:
    """
    List all current Graph subscriptions with detailed information.
    
    Returns:
        List of subscriptions with status
    """
    try:
        subscriptions = graph_service.list_subscriptions()
        
        # Add detailed status info
        now = datetime.now(timezone.utc)
        detailed_subs = []
        
        for sub in subscriptions:
            expiration = sub.get("expirationDateTime")
            if expiration:
                try:
                    if isinstance(expiration, str):
                        exp_dt = datetime.fromisoformat(expiration.replace('Z', '+00:00'))
                    else:
                        exp_dt = expiration
                    
                    time_until_expiry = exp_dt - now
                    is_expired = time_until_expiry.total_seconds() <= 0
                    
                    detailed_subs.append({
                        **sub,
                        "detailed_info": {
                            "expires_in_minutes": int(time_until_expiry.total_seconds() / 60),
                            "is_expired": is_expired,
                            "status": "expired" if is_expired else "active",
                            "resource_type": "teams_messages" if "/teams/" in sub.get("resource", "") and "/messages" in sub.get("resource", "") else "other"
                        }
                    })
                except Exception as e:
                    detailed_subs.append({
                        **sub,
                        "detailed_info": {
                            "parse_error": str(e)
                        }
                    })
        
        return {
            "count": len(subscriptions),
            "subscriptions": detailed_subs,
            "current_utc": now.isoformat()
        }
    except Exception as e:
        logger.error(f"Error listing subscriptions: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cleanup-expired")
async def cleanup_expired_subscriptions() -> Dict[str, Any]:
    """
    Delete all expired subscriptions.
    
    Returns:
        Summary of cleanup operation
    """
    try:
        subscriptions = graph_service.list_subscriptions()
        deleted = []
        failed = []
        
        now = datetime.now(timezone.utc)
        
        for sub in subscriptions:
            sub_id = sub.get("id")
            expiration = sub.get("expirationDateTime")
            
            if not sub_id or not expiration:
                continue
            
            try:
                if isinstance(expiration, str):
                    exp_dt = datetime.fromisoformat(expiration.replace('Z', '+00:00'))
                else:
                    exp_dt = expiration
                
                if (exp_dt - now).total_seconds() <= 0:
                    graph_service.delete_subscription(sub_id)
                    deleted.append({
                        "id": sub_id,
                        "resource": sub.get("resource")
                    })
            except Exception as e:
                failed.append({
                    "id": sub_id,
                    "error": str(e)
                })
        
        return {
            "total_checked": len(subscriptions),
            "deleted": len(deleted),
            "failed": len(failed),
            "deleted_ids": deleted,
            "failed_ids": failed
        }
    except Exception as e:
        logger.error(f"Error cleaning up subscriptions: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
