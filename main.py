"""FastAPI application entry point for Teams-Notion middleware."""
import logging
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.middleware import Middleware
from fastapi.middleware.gzip import GZipMiddleware
from routes import webhooks, subscription, diagnostics, pre_validation
from config import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

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
    """Health check endpoint."""
    return {"status": "healthy"}


@app.on_event("startup")
async def startup_event():
    """Startup event handler."""
    logger.info("Starting Teams-Notion Webhook Middleware")
    logger.info(f"Notion Database ID: {settings.notion_database_id}")
    logger.info(f"Allowed users: {len(settings.allowed_users)} user(s)")
    logger.info(f"Webhook notification URL: {settings.webhook_notification_url}")


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
    uvicorn.run(app, host="0.0.0.0", port=8000)
