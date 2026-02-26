"""
Cache Stats API Endpoint

Provides admin-only access to cache performance statistics.
"""

import logging

from fastapi import APIRouter, Depends

from api.auth import require_admin
from bot.utils.cache import get_all_cache_stats

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/api/cache/stats", dependencies=[Depends(require_admin)])
async def cache_stats():
    """
    Get cache statistics for all registered cache functions, grouped by namespace.

    Returns:
        JSON with cache stats per namespace and function.
    """
    return {"stats": get_all_cache_stats()}
