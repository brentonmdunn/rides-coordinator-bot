"""Feature Flags API Routes - Example Backend with Hardcoded Data."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from api.dummy_data import FEATURE_FLAGS

router = APIRouter()


class FeatureFlagUpdate(BaseModel):
    """Request model for updating a feature flag."""

    enabled: bool


@router.get("/api/feature-flags")
async def list_feature_flags():
    """
    List all feature flags and their current status.

    Returns hardcoded dummy data for portfolio demonstration.
    """
    return FEATURE_FLAGS


@router.put("/api/feature-flags/{feature_name}")
async def toggle_feature_flag(feature_name: str, update: FeatureFlagUpdate):
    """
    Mock toggle feature flag - returns success but doesn't persist changes.

    In the real app, this would update the database.
    """
    # Find the flag in our dummy data
    flag = next(
        (f for f in FEATURE_FLAGS["flags"] if f["feature"] == feature_name), None
    )

    if not flag:
        raise HTTPException(
            status_code=404, detail=f"Feature flag '{feature_name}' not found"
        )

    # Check if already in desired state
    if flag["enabled"] == update.enabled:
        return {
            "success": False,
            "message": (
                f"Feature flag '{feature_name}' is already "
                f"{'enabled' if update.enabled else 'disabled'}"
            ),
            "flag": flag,
        }

    # Mock update (doesn't actually persist)
    return {
        "success": True,
        "message": (
            f"Feature flag '{feature_name}' is now "
            f"{'enabled' if update.enabled else 'disabled'} (mock - not persisted)"
        ),
        "flag": {
            "id": flag["id"],
            "feature": flag["feature"],
            "enabled": update.enabled,  # Show the new state even though not persisted
        },
    }
