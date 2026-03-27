"""
FastAPI application entry point.

Main application setup with lifespan management, middleware,
and route registration.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.api.endpoints import router
from app.monitoring import (
    MetricsMiddleware,
    LogContextMiddleware,
    metrics_endpoint,
    configure_logging,
)
from app.db.connection import init_db, close_db

# Configure logging
configure_logging()

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    
    Handles startup and shutdown events.
    """
    settings = get_settings()
    
    logger.info(
        "Application starting",
        extra={
            "app_name": settings.app_name,
            "version": settings.app_version,
            "environment": settings.environment
        }
    )
    
    # Startup
    try:
        # Initialize database
        await init_db()
        logger.info("Database initialized")
        
        # Initialize services
        # Services are initialized lazily on first request
        
        logger.info("Application started successfully")
        
    except Exception as e:
        logger.error(f"Startup failed: {e}")
        raise
    
    yield
    
    # Shutdown
    logger.info("Application shutting down")
    
    try:
        await close_db()
        logger.info("Database connection closed")
        
    except Exception as e:
        logger.error(f"Shutdown error: {e}")
    
    logger.info("Application shutdown complete")


def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application.
    
    Returns:
        Configured FastAPI application instance
    """
    settings = get_settings()
    
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="A verified, self-expanding developer knowledge base",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.security.allowed_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Add metrics middleware
    app.add_middleware(MetricsMiddleware)
    
    # Add logging context middleware
    app.add_middleware(LogContextMiddleware)
    
    # Register API routes
    app.include_router(router, prefix="/api")
    
    # Also mount routes at root for backwards compatibility
    app.include_router(router)
    
    # Prometheus metrics endpoint
    app.add_api_route("/metrics", metrics_endpoint, methods=["GET"])
    
    # Exception handlers
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        """Global exception handler."""
        logger.error(
            f"Unhandled exception: {exc}",
            extra={
                "path": request.url.path,
                "method": request.method
            }
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "An unexpected error occurred"
                }
            }
        )
    
    return app


# Create the application instance
app = create_app()


# For running with uvicorn directly
if __name__ == "__main__":
    import uvicorn
    
    settings = get_settings()
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
        log_level=settings.monitoring.log_level.lower()
    )

