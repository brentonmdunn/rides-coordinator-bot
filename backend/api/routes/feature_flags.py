"""
Feature Flags API Endpoints

Provides API access to feature flag management (admin only).
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.auth import require_admin
from bot.core.enums import CacheNamespace
from bot.services.feature_flags_service import FeatureFlagsService
from bot.utils.cache import invalidate_namespace

logger = logging.getLogger(__name__)

router = APIRouter()


class FeatureFlagUpdate(BaseModel):
    """Request model for updating a feature flag."""

    enabled: bool


@router.get("/api/feature-flags", dependencies=[Depends(require_admin)])
async def list_feature_flags():
    """
    List all feature flags and their current status.

    Returns:
        JSON with list of all feature flags
    """
    try:
        flags = await FeatureFlagsService.list_flags()

        return {
            "flags": [
                {"id": flag.id, "feature": flag.feature, "enabled": flag.enabled} for flag in flags
            ]
        }
    except Exception as e:
        logger.exception("Error fetching feature flags")
        raise HTTPException(status_code=500, detail=f"Failed to fetch feature flags: {e!s}") from e


@router.put("/api/feature-flags/{feature_name}", dependencies=[Depends(require_admin)])
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
        flag = await FeatureFlagsService.get_flag(feature_name)

        if not flag:
            raise HTTPException(status_code=404, detail=f"Feature flag '{feature_name}' not found")

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

        svc = FeatureFlagsService()
        await svc.modify_feature_flag(feature_name, update.enabled)
        await FeatureFlagsService.reinitialize_cache()
        await invalidate_namespace(CacheNamespace.ASK_RIDES_STATUS)

        updated_flag = await FeatureFlagsService.get_flag(feature_name)

        logger.info(f"Feature flag '{feature_name}' {'enabled' if update.enabled else 'disabled'}")

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
        logger.exception("Error toggling feature flag")
        raise HTTPException(status_code=500, detail=f"Failed to toggle feature flag: {e!s}") from e
