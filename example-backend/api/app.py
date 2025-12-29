"""
FastAPI Application - Portfolio Example Backend

Simplified backend for portfolio demonstration with hardcoded data.
No Discord bot, no authentication, no database - just API endpoints.
"""

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from api.routes.ask_rides import router as ask_rides_router
from api.routes.check_pickups import router as check_pickups_router
from api.routes.feature_flags import router as feature_flags_router
from api.routes.group_rides import router as group_rides_router
from api.routes.health import router as health_router
from api.routes.list_pickups import router as list_pickups_router

# Create FastAPI application
app = FastAPI(
    title="Rides Coordinator - Portfolio Example",
    description="Portfolio demonstration backend with hardcoded dummy data",
    version="1.0.0",
)

# Add CORS middleware (allows frontend from any origin for demo purposes)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health_router)
app.include_router(ask_rides_router)
app.include_router(check_pickups_router)
app.include_router(feature_flags_router)
app.include_router(group_rides_router)
app.include_router(list_pickups_router)

# Mount static files for React SPA (if directory exists)
admin_ui_path = Path("admin_ui")
if admin_ui_path.is_dir():
    # Mount assets directory
    assets_path = admin_ui_path / "assets"
    if assets_path.is_dir():
        app.mount("/assets", StaticFiles(directory=assets_path), name="assets")

    # Catch-all route for SPA
    @app.get("/{file_path:path}")
    async def serve_spa(file_path: str):
        """
        Serve React SPA files with fallback to index.html.
        Excludes API routes.
        """
        # Allow API routes to pass through
        if (
            file_path.startswith("api/")
            or file_path.startswith("docs")
            or file_path.startswith("openapi.json")
        ):
            return None

        # Check if the requested path corresponds to a file
        full_path = admin_ui_path / file_path
        if file_path and full_path.is_file():
            return FileResponse(full_path)

        # Otherwise, serve the SPA index.html
        index_path = admin_ui_path / "index.html"
        if index_path.is_file():
            return FileResponse(index_path)

        # If no index.html, return 404
        raise HTTPException(status_code=404, detail="Not Found")
