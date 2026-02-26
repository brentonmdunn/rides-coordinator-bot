"""
Admin Users API Endpoints

Provides admin-only access to user account management.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.auth import require_admin
from bot.core.enums import AccountRoles
from bot.repositories.user_accounts_repository import UserAccountsRepository

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin", tags=["admin"])


class UpdateRoleRequest(BaseModel):
    """Request model for updating a user's role."""

    role: str


@router.get("/users", dependencies=[Depends(require_admin)])
async def list_users():
    """List all user accounts (admin only).

    Returns:
        JSON with list of all user accounts.
    """
    accounts = await UserAccountsRepository.get_all_accounts()
    return {
        "users": [
            {
                "id": account.id,
                "email": account.email,
                "role": account.role,
                "created_at": account.created_at.isoformat() if account.created_at else None,
            }
            for account in accounts
        ]
    }


@router.put("/users/{email}/role", dependencies=[Depends(require_admin)])
async def update_user_role(email: str, body: UpdateRoleRequest):
    """Update a user's role (admin only).

    Args:
        email: The email of the user to update.
        body: Contains the new role.

    Returns:
        JSON with the updated user info.
    """
    valid_roles = tuple(r.value for r in AccountRoles)
    if body.role not in valid_roles:
        raise HTTPException(
            status_code=400,
            detail=f"role must be one of: {', '.join(valid_roles)}",
        )

    updated = await UserAccountsRepository.update_role(email, body.role)
    if not updated:
        raise HTTPException(status_code=404, detail=f"User '{email}' not found")

    logger.info(f"👤 Admin updated role for '{email}' to '{body.role}'")
    return {"email": updated.email, "role": updated.role}
