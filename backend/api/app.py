"""
FastAPI Application

Main FastAPI application with Discord bot integration and Cloudflare authentication.
"""

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from api.auth import cloudflare_access_middleware
from api.routes.ask_rides import router as ask_rides_router
from api.routes.check_pickups import router as check_pickups_router
from api.routes.example import router as example_router
from api.routes.feature_flags import router as feature_flags_router
from api.routes.group_rides import router as group_rides_router
from api.routes.health import router as health_router
from api.routes.list_pickups import router as list_pickups_router
from api.routes.locations import router as locations_router
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
            logger.error(
                "CRITICAL: Cloudflare Access environment variables are not set. "
                "Authentication will fail."
            )

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
admin_ui_path = Path("admin_ui")
if admin_ui_path.is_dir():
    # Mount assets directory
    assets_path = admin_ui_path / "assets"
    if assets_path.is_dir():
        app.mount("/assets", StaticFiles(directory=assets_path), name="assets")
        logger.info(f"Mounted static assets from {assets_path}")

    # Catch-all route for SPA
    @app.get("/{file_path:path}")
    async def serve_spa(file_path: str):
        """
        Serve React SPA files with fallback to index.html.
        Excludes API routes.

        Args:
            file_path: Requested file path

        Returns:
            File response for requested file or index.html
        """
        # Allow API routes to pass through (though they should be caught by routers above)
        if (
            file_path.startswith("api/")
            or file_path.startswith("docs")
            or file_path.startswith("openapi.json")
        ):
            return None

        # Check if the requested path corresponds to a file in admin_ui
        full_path = admin_ui_path / file_path
        if file_path and full_path.is_file():
            return FileResponse(full_path)
        # Otherwise, serve the SPA index.html
        index_path = admin_ui_path / "index.html"
        if index_path.is_file():
            return FileResponse(index_path)
        # If no index.html, return 404
        raise HTTPException(status_code=404, detail="Not Found")

    logger.info("Configured SPA serving from admin_ui/")
else:
    logger.warning("Admin UI directory not found. SPA will not be served.")
