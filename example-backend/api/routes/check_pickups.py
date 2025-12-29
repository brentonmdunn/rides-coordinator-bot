"""Check Pickups API Routes - Example Backend with Hardcoded Data."""

from fastapi import APIRouter

from api.dummy_data import DRIVER_REACTIONS, FRIDAY_COVERAGE, SUNDAY_COVERAGE

router = APIRouter(prefix="/api/check-pickups", tags=["check-pickups"])


@router.get("/{ride_type}")
async def get_pickup_coverage(ride_type: str):
    """
    Check ride coverage for users who reacted to a ride message.

    Returns hardcoded dummy data for portfolio demonstration.
    """
    if ride_type.lower() == "friday":
        return FRIDAY_COVERAGE
    elif ride_type.lower() == "sunday":
        return SUNDAY_COVERAGE
    else:
        return {
            "users": [],
            "total": 0,
            "assigned": 0,
            "message_found": False,
            "has_coverage_entries": False,
        }


@router.post("/sync")
async def sync_ride_coverage():
    """
    Mock sync endpoint - returns success but doesn't actually do anything.

    In the real app, this would scan Discord messages.
    """
    return {
        "success": True,
        "message": "Ride coverage sync completed (mock)",
        "updates": 0,
    }


@router.get("/driver-reactions/{day}")
async def get_driver_reactions(day: str):
    """
    Get emoji reactions for driver messages.

    Returns hardcoded dummy data for portfolio demonstration.
    """
    day_lower = day.lower()
    if day_lower in DRIVER_REACTIONS:
        return DRIVER_REACTIONS[day_lower]
    else:
        return {"day": day, "reactions": {}, "message_found": False}
