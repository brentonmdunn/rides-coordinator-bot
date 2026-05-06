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
from api.auth_session import session_cookie_middleware
from api.middleware.access_logger import AccessLogMiddleware
from api.routes.admin_users import router as admin_users_router
from api.routes.ask_rides import router as ask_rides_router
from api.routes.auth_discord import router as auth_discord_router
from api.routes.cache_stats import router as cache_stats_router
from api.routes.check_pickups import router as check_pickups_router
from api.routes.example import router as example_router
from api.routes.feature_flags import router as feature_flags_router
from api.routes.group_rides import router as group_rides_router
from api.routes.health import router as health_router
from api.routes.list_pickups import router as list_pickups_router
from api.routes.locations import router as locations_router
from api.routes.me import router as me_router
from api.routes.route_builder import router as route_builder_router
from api.routes.user_preferences import router as user_preferences_router
from api.routes.usernames import router as usernames_router
from bot.api import bot_lifespan

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Environment configuration
CLOUDFLARE_TEAM_DOMAIN = os.getenv("CLOUDFLARE_TEAM_DOMAIN")
CLOUDFLARE_AUD = os.getenv("CLOUDFLARE_AUD")
APP_ENV = os.getenv("APP_ENV", "local")
AUTH_PROVIDER = os.getenv("AUTH_PROVIDER", "cloudflare")  # "cloudflare" | "self"


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
        if AUTH_PROVIDER == "self":
            logger.info("Auth provider: self-hosted Discord OAuth + session cookies.")
        elif not CLOUDFLARE_TEAM_DOMAIN or not CLOUDFLARE_AUD:
            logger.error(
                "CRITICAL: Cloudflare Access environment variables are not set. "
                "Authentication will fail."
            )
        else:
            logger.info("Auth provider: Cloudflare Access.")
    else:
        logger.info("Running in LOCAL mode: Authentication is bypassed.")

    # Start Discord bot
    async with bot_lifespan():
        yield

    # Shutdown (cleanup handled by bot_lifespan context manager)
    logger.info("Application shutdown complete")


# Create FastAPI application
app = FastAPI(lifespan=lifespan)

# Add authentication middleware based on AUTH_PROVIDER.
# Must be registered BEFORE CORS so that CORS (added last) becomes the
# outermost layer and attaches Access-Control-Allow-Origin to every response,
# including 401s returned directly by the auth middleware.
if AUTH_PROVIDER == "self":
    app.middleware("http")(session_cookie_middleware)
    app.include_router(auth_discord_router)
    logger.info("Using self-hosted Discord OAuth middleware")
else:
    app.middleware("http")(cloudflare_access_middleware)
    logger.info("Using Cloudflare Access middleware")

# Add access logging middleware
app.add_middleware(AccessLogMiddleware)
logger.info("Access logging middleware enabled")

# Add CORS middleware last so it is outermost and adds CORS headers to all
# responses, including 401s emitted by the auth middleware above.
if APP_ENV == "local":
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://localhost:5174"],  # Vite dev server
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    logger.info("CORS enabled for local development")

# Include routers
app.include_router(health_router)
if APP_ENV == "local":
    app.include_router(example_router)
app.include_router(locations_router)
app.include_router(feature_flags_router)
app.include_router(me_router)
app.include_router(ask_rides_router)
app.include_router(cache_stats_router)
app.include_router(group_rides_router)
app.include_router(list_pickups_router)
app.include_router(check_pickups_router)
app.include_router(route_builder_router)
app.include_router(admin_users_router)
app.include_router(user_preferences_router)
app.include_router(usernames_router)

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
        # Otherwise, serve the SPA index.html.
        # no-store prevents browsers from caching index.html across deploys,
        # which would cause old hashed asset URLs to 404 and break the page.
        index_path = admin_ui_path / "index.html"
        if index_path.is_file():
            return FileResponse(index_path, headers={"Cache-Control": "no-store"})
        # If no index.html, return 404
        raise HTTPException(status_code=404, detail="Not Found")

    logger.info("Configured SPA serving from admin_ui/")
else:
    logger.warning("Admin UI directory not found. SPA will not be served.")
