"""
Feature Flags API Endpoints

Provides API access to feature flag management.
"""

import logging
import os

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from api.constants import ADMIN_EMAILS
from bot.core.enums import CacheNamespace
from bot.repositories.feature_flags_repository import FeatureFlagsRepository
from bot.utils.cache import invalidate_namespace

logger = logging.getLogger(__name__)
router = APIRouter()
APP_ENV = os.getenv("APP_ENV", "local")


async def require_admin_email(request: Request):
    """Dependency that restricts access to the admin email."""
    user = getattr(request.state, "user", None) or {}
    email = user.get("email", "")
    allowed = ADMIN_EMAILS | ({"dev@example.com"} if APP_ENV == "local" else set())
    if email not in allowed:
        raise HTTPException(status_code=403, detail="Forbidden")
    return email


class FeatureFlagUpdate(BaseModel):
    """Request model for updating a feature flag."""

    enabled: bool


@router.get("/api/feature-flags", dependencies=[Depends(require_admin_email)])
async def list_feature_flags():
    """
    List all feature flags and their current status.

    Returns:
        JSON with list of all feature flags
    """
    try:
        flags = await FeatureFlagsRepository.get_all_feature_flags()

        return {
            "flags": [
                {"id": flag.id, "feature": flag.feature, "enabled": flag.enabled} for flag in flags
            ]
        }
    except Exception as e:
        logger.exception(f"Error fetching feature flags: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch feature flags: {e!s}") from e


@router.put("/api/feature-flags/{feature_name}", dependencies=[Depends(require_admin_email)])
async def toggle_feature_flag(feature_name: str, update: FeatureFlagUpdate):
    """
    Toggle a feature flag on or off.

    Args:
        feature_name: Name of the feature flag to update
        update: Contains the new enabled status

    Returns:
        JSON with success status and updated flag info
    """
    try:
        # Get current flag
        flag = await FeatureFlagsRepository.get_feature_flag(feature_name)

        if not flag:
            raise HTTPException(status_code=404, detail=f"Feature flag '{feature_name}' not found")

        # Check if already in desired state
        if flag.enabled == update.enabled:
            return {
                "success": False,
                "message": (
                    f"Feature flag '{feature_name}' is already "
                    f"{'enabled' if update.enabled else 'disabled'}"
                ),
                "flag": {
                    "id": flag.id,
                    "feature": flag.feature,
                    "enabled": flag.enabled,
                },
            }

        # Update the flag
        await FeatureFlagsRepository.update_feature_flag(feature_name, update.enabled)

        # Refresh caches
        await FeatureFlagsRepository.initialize_cache()
        invalidate_namespace(CacheNamespace.ASK_RIDES_STATUS)

        # Get updated flag
        updated_flag = await FeatureFlagsRepository.get_feature_flag(feature_name)

        logger.info(
            f"✅ Feature flag '{feature_name}' {'enabled' if update.enabled else 'disabled'}"
        )

        return {
            "success": True,
            "message": (
                f"Feature flag '{feature_name}' is now "
                f"{'enabled' if update.enabled else 'disabled'}"
            ),
            "flag": {
                "id": updated_flag.id,
                "feature": updated_flag.feature,
                "enabled": updated_flag.enabled,
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error toggling feature flag: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to toggle feature flag: {e!s}") from e
