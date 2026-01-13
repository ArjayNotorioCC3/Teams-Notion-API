"""FastAPI application entry point for Teams-Notion middleware."""
import logging
import asyncio
import os
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.middleware import Middleware
from fastapi.middleware.gzip import GZipMiddleware
from routes import webhooks, subscription, diagnostics, pre_validation, keep_alive
from services.graph_service import GraphService
from services.notion_service import NotionService
from config import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Create service singletons at module level for reuse across all requests
graph_service = GraphService()
notion_service = NotionService()

# Make services available to keep_alive module
keep_alive.set_services(graph_service, notion_service)

# Create FastAPI app with optimizations
app = FastAPI(
    title="Teams-Notion Webhook Middleware",
    description="Middleware for automating ticket creation in Notion from Microsoft Teams",
    version="1.0.0",
    # Optimize for fast responses
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    # Disable unnecessary features for performance
    default_response_class=JSONResponse,
)

# Add GZip compression middleware for faster responses
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Include routers
app.include_router(webhooks.router)
app.include_router(subscription.router)
app.include_router(diagnostics.router)
app.include_router(pre_validation.router)
app.include_router(keep_alive.router)


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "name": "Teams-Notion Webhook Middleware",
        "version": "1.0.0",
        "status": "running"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint for Render and monitoring."""
    return {"status": "healthy"}


@app.on_event("startup")
async def startup_event():
    """Startup event handler - pre-warm services to prevent cold starts."""
    logger.info("Starting Teams-Notion Webhook Middleware")
    logger.info(f"Notion Database ID: {settings.notion_database_id}")
    logger.info(f"Allowed users: {len(settings.allowed_users)} user(s)")
    logger.info(f"Webhook notification URL: {settings.webhook_notification_url}")
    
    # Pre-warm GraphService by acquiring access token
    logger.info("Pre-warming GraphService - acquiring access token...")
    try:
        graph_service._get_access_token()
        logger.info("GraphService warmup complete - access token acquired")
    except Exception as e:
        logger.error(f"GraphService warmup failed: {str(e)}")
    
    # Initialize NotionService
    logger.info("Initializing NotionService...")
    logger.info("NotionService initialized")
    
    # Start background keep-alive task
    keep_alive_enabled = os.getenv("KEEP_ALIVE_ENABLED", "true").lower() == "true"
    if keep_alive_enabled:
        logger.info("Starting background keep-alive task")
        asyncio.create_task(background_keep_alive())
    else:
        logger.info("Background keep-alive disabled")


@app.on_event("shutdown")
async def shutdown_event():
    """Shutdown event handler."""
    logger.info("Shutting down Teams-Notion Webhook Middleware")


async def background_keep_alive():
    """
    Background task to keep service warm and prevent cold starts.
    Pings /health endpoint every 10 minutes to keep service active on Render free tier.
    """
    import httpx
    
    keep_alive_interval = int(os.getenv("KEEP_ALIVE_INTERVAL_SECONDS", "600"))
    logger.info(f"Keep-alive task running - interval: {keep_alive_interval}s")
    
    # Ping self to keep service warm
    port = int(os.getenv("PORT", "10000"))
    base_url = f"http://localhost:{port}"
    
    async with httpx.AsyncClient() as client:
        while True:
            try:
                await asyncio.sleep(keep_alive_interval)
                response = await client.get(f"{base_url}/health", timeout=5.0)
                if response.status_code == 200:
                    logger.debug("Keep-alive ping successful")
            except Exception as e:
                logger.warning(f"Keep-alive ping failed: {str(e)}")


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler."""
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
