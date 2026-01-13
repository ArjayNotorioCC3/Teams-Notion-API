"""Keep-alive and warmup routes for preventing cold starts."""
import logging
import asyncio
from typing import Optional
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from services.graph_service import GraphService
from services.notion_service import NotionService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/keep-alive", tags=["keep-alive"])

# Global service instances (will be initialized in main.py)
graph_service: Optional[GraphService] = None
notion_service: Optional[NotionService] = None


def set_services(graph_svc: GraphService, notion_svc: NotionService):
    """
    Set global service instances for warmup access.
    
    Args:
        graph_svc: GraphService instance
        notion_svc: NotionService instance
    """
    global graph_service, notion_service
    graph_service = graph_svc
    notion_service = notion_svc


@router.get("/ping")
async def ping() -> JSONResponse:
    """
    Simple ping endpoint to keep service warm.
    Does minimal work to prevent cold start.
    
    Returns:
        Success response
    """
    return JSONResponse(
        status_code=200,
        content={"status": "ok", "message": "Service is warm"}
    )


@router.get("/warmup")
async def warmup() -> JSONResponse:
    """
    Warmup endpoint that initializes all services and acquires tokens.
    Call this before creating subscriptions to ensure fast response times.
    
    This endpoint:
    - Acquires Microsoft Graph access token
    - Initializes Notion service
    - Tests connectivity to both services
    
    Returns:
        Warmup status with token acquisition time
    """
    import time
    
    if not graph_service or not notion_service:
        raise HTTPException(
            status_code=503,
            detail="Services not initialized. Call this endpoint after app startup."
        )
    
    start_time = time.time()
    warmup_info = {
        "status": "warming",
        "services": {}
    }
    
    # Warm up GraphService (acquire access token)
    try:
        logger.info("Warming up GraphService - acquiring access token")
        token_start = time.time()
        graph_service._get_access_token()
        token_time = (time.time() - token_start) * 1000
        logger.info(f"GraphService warmup complete - token acquired in {token_time:.2f}ms")
        warmup_info["services"]["graph"] = {
            "status": "ready",
            "token_acquisition_time_ms": round(token_time, 2)
        }
    except Exception as e:
        logger.error(f"GraphService warmup failed: {str(e)}")
        warmup_info["services"]["graph"] = {
            "status": "error",
            "error": str(e)
        }
    
    # Warm up NotionService (test connectivity)
    try:
        logger.info("Warming up NotionService - testing connectivity")
        notion_start = time.time()
        notion_service._make_request("GET", "/users/me")
        notion_time = (time.time() - notion_start) * 1000
        logger.info(f"NotionService warmup complete - connectivity test took {notion_time:.2f}ms")
        warmup_info["services"]["notion"] = {
            "status": "ready",
            "connectivity_test_time_ms": round(notion_time, 2)
        }
    except Exception as e:
        logger.warning(f"NotionService warmup failed: {str(e)}")
        warmup_info["services"]["notion"] = {
            "status": "error",
            "error": str(e)
        }
    
    total_time = (time.time() - start_time) * 1000
    warmup_info["total_warmup_time_ms"] = round(total_time, 2)
    warmup_info["status"] = "ready"
    
    logger.info(f"Warmup complete - total time: {total_time:.2f}ms")
    
    return JSONResponse(status_code=200, content=warmup_info)


@router.get("/status")
async def status() -> JSONResponse:
    """
    Check warmup status of services.
    
    Returns:
        Status of all services and token availability
    """
    if not graph_service or not notion_service:
        return JSONResponse(
            status_code=200,
            content={
                "status": "services_not_initialized",
                "services": {
                    "graph": "not_initialized",
                    "notion": "not_initialized"
                }
            }
        )
    
    status_info = {
        "status": "checked",
        "services": {}
    }
    
    # Check GraphService token status
    try:
        if graph_service._access_token and graph_service._token_expires_at:
            from datetime import datetime, timezone, timedelta
            time_until_expiry = graph_service._token_expires_at - datetime.now(timezone.utc)
            status_info["services"]["graph"] = {
                "token_available": True,
                "expires_in_seconds": int(time_until_expiry.total_seconds())
            }
        else:
            status_info["services"]["graph"] = {
                "token_available": False,
                "expires_in_seconds": None
            }
    except Exception as e:
        status_info["services"]["graph"] = {
            "token_available": False,
            "error": str(e)
        }
    
    # Check NotionService
    status_info["services"]["notion"] = {
        "initialized": True,
        "database_id": notion_service.database_id
    }
    
    return JSONResponse(status_code=200, content=status_info)
