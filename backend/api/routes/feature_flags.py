"""
Feature Flags API Endpoints

Provides API access to feature flag management.
"""

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from bot.repositories.feature_flags_repository import FeatureFlagsRepository

logger = logging.getLogger(__name__)
router = APIRouter()


class FeatureFlagUpdate(BaseModel):
    """Request model for updating a feature flag."""
    enabled: bool


@router.get("/api/feature-flags")
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
                {
                    "id": flag.id,
                    "feature": flag.feature,
                    "enabled": flag.enabled
                }
                for flag in flags
            ]
        }
    except Exception as e:
        logger.exception(f"Error fetching feature flags: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch feature flags: {str(e)}"
        )


@router.put("/api/feature-flags/{feature_name}")
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
            raise HTTPException(
                status_code=404,
                detail=f"Feature flag '{feature_name}' not found"
            )
        
        # Check if already in desired state
        if flag.enabled == update.enabled:
            return {
                "success": False,
                "message": f"Feature flag '{feature_name}' is already {'enabled' if update.enabled else 'disabled'}",
                "flag": {
                    "id": flag.id,
                    "feature": flag.feature,
                    "enabled": flag.enabled
                }
            }
        
        # Update the flag
        await FeatureFlagsRepository.update_feature_flag(feature_name, update.enabled)
        
        # Refresh cache
        await FeatureFlagsRepository.initialize_cache()
        
        # Get updated flag
        updated_flag = await FeatureFlagsRepository.get_feature_flag(feature_name)
        
        logger.info(f"✅ Feature flag '{feature_name}' {'enabled' if update.enabled else 'disabled'}")
        
        return {
            "success": True,
            "message": f"Feature flag '{feature_name}' is now {'enabled' if update.enabled else 'disabled'}",
            "flag": {
                "id": updated_flag.id,
                "feature": updated_flag.feature,
                "enabled": updated_flag.enabled
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error toggling feature flag: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to toggle feature flag: {str(e)}"
        )
