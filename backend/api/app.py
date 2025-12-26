"""
FastAPI Application

Main FastAPI application with Discord bot integration and Cloudflare authentication.
"""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from api.auth import cloudflare_access_middleware
from api.routes.ask_rides import router as ask_rides_router
from api.routes.example import router as example_router
from api.routes.feature_flags import router as feature_flags_router
from api.routes.group_rides import router as group_rides_router
from api.routes.health import router as health_router
from api.routes.locations import router as locations_router
from api.routes.list_pickups import router as list_pickups_router
from api.routes.check_pickups import router as check_pickups_router
from bot.api import bot_lifespan

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Environment configuration
CLOUDFLARE_TEAM_DOMAIN = os.getenv("CLOUDFLARE_TEAM_DOMAIN")
CLOUDFLARE_AUD = os.getenv("CLOUDFLARE_AUD")
APP_ENV = os.getenv("APP_ENV", "local")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage application and Discord bot lifecycle.
    
    Args:
        app: The FastAPI application instance
        
    Yields:
        Control back to the application during runtime
    """
    # Startup
    if APP_ENV != "local":
        if not CLOUDFLARE_TEAM_DOMAIN or not CLOUDFLARE_AUD:
            logger.error("CRITICAL: Cloudflare Access environment variables are not set. Authentication will fail.")
        else:
            logger.info("Cloudflare Access configured for production.")
    else:
        logger.info("Running in LOCAL mode: Authentication is bypassed.")
    
    # Start Discord bot
    async with bot_lifespan():
        yield
    
    # Shutdown (cleanup handled by bot_lifespan context manager)
    logger.info("Application shutdown complete")


# Create FastAPI application
app = FastAPI(lifespan=lifespan)

# Add CORS middleware for development (allows frontend on different port)
if APP_ENV == "local":
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://localhost:5174"],  # Vite dev server
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    logger.info("CORS enabled for local development")

# Add Cloudflare authentication middleware
app.middleware("http")(cloudflare_access_middleware)

# Include routers
app.include_router(health_router)
app.include_router(example_router)
app.include_router(locations_router)
app.include_router(feature_flags_router)
app.include_router(ask_rides_router)
app.include_router(group_rides_router)
app.include_router(list_pickups_router)
app.include_router(check_pickups_router)

# Mount static files for React SPA (if directory exists)
admin_ui_path = "admin_ui"
if os.path.isdir(admin_ui_path):
    # Mount assets directory
    assets_path = os.path.join(admin_ui_path, "assets")
    if os.path.isdir(assets_path):
        app.mount("/assets", StaticFiles(directory=assets_path), name="assets")
        logger.info(f"Mounted static assets from {assets_path}")
    
    # SPA fallback route - must be last
    @app.get("/{file_path:path}")
    def serve_spa(file_path: str):
        """
        Serve React SPA files with fallback to index.html.
        Excludes API routes.
        
        Args:
            file_path: Requested file path
            
        Returns:
            File response for requested file or index.html
        """
        logger.error("HERERERERERERE")
        # Don't intercept API routes
        if file_path.startswith("api/"):
            return {"error": "Not found"}
        
        # Check if the requested path corresponds to a file in admin_ui
        full_path = os.path.join(admin_ui_path, file_path)
        if file_path and os.path.isfile(full_path):
            return FileResponse(full_path)
        # Otherwise, serve the SPA index.html
        index_path = os.path.join(admin_ui_path, "index.html")
        if os.path.isfile(index_path):
            return FileResponse(index_path)
        # If no index.html, return 404
        return {"error": "SPA not found"}
    
    logger.info("Configured SPA serving from admin_ui/")
else:
    logger.warning(f"Admin UI directory '{admin_ui_path}' not found. Static file serving disabled.")
