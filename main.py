"""FastAPI application entry point for Teams-Notion middleware."""
import logging
import os
from urllib.parse import unquote_plus
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.middleware import Middleware
from fastapi.middleware.gzip import GZipMiddleware
from routes import webhooks, subscription, diagnostics
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

# CRITICAL: Ultra-fast validation endpoint for Microsoft Graph
# This endpoint MUST be registered BEFORE middleware and routers
# Zero overhead for validation: no logging, no services, no middleware delays
@app.api_route("/graph/validate", methods=["GET", "POST"])
async def graph_validation(request: Request):
    """
    Ultra-fast validation endpoint for Microsoft Graph webhook subscriptions.
    
    This endpoint bypasses all middleware, JSON handling, and router overhead for validation.
    It responds immediately with the decoded validation token in plain text format.
    For actual notifications, it forwards to the webhook notification handler.
    
    Returns:
        Plain text validation token (decoded) for validation requests
        Processed response from webhook handler for actual notifications
    """
    # CRITICAL: Check for validation token FIRST - fastest path possible
    # FastAPI's query_params.get() automatically decodes, but unquote_plus ensures it
    token = request.query_params.get("validationToken")
    if token:
        # Return decoded token immediately - NO logging, NO processing, NO delays
        # This is the critical path that must be <1ms
        return PlainTextResponse(unquote_plus(token), media_type="text/plain")
    
    # If no validation token, this is an actual notification
    # Forward to webhook notification handler for processing
    # Import here to avoid circular imports and keep validation path fast
    from routes.webhooks import webhook_notification
    
    # Forward the request to the webhook notification handler
    # This allows notifications to be processed while keeping validation ultra-fast
    return await webhook_notification(request)

# Add GZip compression middleware for faster responses
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Include routers
app.include_router(webhooks.router)
app.include_router(subscription.router)
app.include_router(diagnostics.router)


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
    """Health check endpoint for monitoring."""
    return {"status": "healthy"}


@app.on_event("startup")
async def startup_event():
    """Startup event handler - initialize services."""
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


@app.on_event("shutdown")
async def shutdown_event():
    """Shutdown event handler."""
    logger.info("Shutting down Teams-Notion Webhook Middleware")


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
