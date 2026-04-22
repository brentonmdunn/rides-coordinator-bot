"""
Cache Stats API Endpoint

Provides admin-only access to cache performance statistics and invalidation.
"""

import logging

from fastapi import APIRouter, Depends

from api.auth import require_admin
from bot.utils.cache import invalidate_all_namespaces

logger = logging.getLogger(__name__)


router = APIRouter()


@router.post("/api/cache/invalidate", dependencies=[Depends(require_admin)])
async def invalidate_cache():
    """
    Invalidate all cache entries across every namespace (admin only).

    Returns:
        JSON with success message.
    """
    await invalidate_all_namespaces()
    logger.info("🗑️ Admin triggered full cache invalidation")
    return {"message": "All cache entries invalidated"}
