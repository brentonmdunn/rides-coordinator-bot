"""
Admin Users API Endpoints

Provides admin-only access to user account management.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from api.auth import require_admin
from api.constants import ADMIN_EMAILS
from bot.core.database import AsyncSessionLocal
from bot.core.enums import AccountRoles
from bot.core.models import UserAccount
from bot.repositories.user_accounts_repository import UserAccountsRepository
from bot.services.user_accounts_service import UserAccountsService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["admin"])


class UpdateRoleRequest(BaseModel):
    """Request model for updating a user's role."""

    role: str


class InviteUserRequest(BaseModel):
    """Request model for inviting a new user by Discord username."""

    discord_username: str
    role: str = AccountRoles.VIEWER


@router.post("/users/invite", dependencies=[Depends(require_admin)])
async def invite_user(body: InviteUserRequest, request: Request):
    """
    Invite a new user by Discord username (admin only).

    Creates a user_accounts row with no email. Email is populated on first Discord login.
    """
    user = getattr(request.state, "user", None) or {}
    invited_by = user.get("email", "")

    valid_roles = tuple(r.value for r in AccountRoles)
    if body.role not in valid_roles:
        raise HTTPException(
            status_code=400,
            detail=f"role must be one of: {', '.join(valid_roles)}",
        )

    account = await UserAccountsService.invite(
        body.discord_username.strip(), AccountRoles(body.role), invited_by
    )
    if account is None:
        raise HTTPException(
            status_code=409,
            detail=f"An account for '{body.discord_username}' already exists.",
        )
    logger.info(f"👤 Admin invited Discord user '{body.discord_username}' with role '{body.role}'")
    return {
        "id": account.id,
        "discord_username": account.discord_username,
        "email": account.email,
        "role": account.role,
        "invited_by": account.invited_by,
    }


@router.delete("/users/{account_id}", dependencies=[Depends(require_admin)])
async def revoke_user(account_id: int, request: Request):
    """
    Remove a user account or revoke a pending invite (admin only).

    Cannot revoke root admins from ADMIN_EMAILS.
    """
    async with AsyncSessionLocal() as session:
        account = await session.get(UserAccount, account_id)

    if not account:
        raise HTTPException(status_code=404, detail="User not found")

    if account.email in ADMIN_EMAILS:
        raise HTTPException(status_code=400, detail="Cannot revoke a root admin.")

    deleted = await UserAccountsService.revoke(account_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="User not found")

    logger.info(f"👤 Admin revoked account id={account_id}")
    return {"ok": True}


@router.get("/users", dependencies=[Depends(require_admin)])
async def list_users(request: Request):
    """
    List all user accounts (admin only).

    Returns:
        JSON with list of all user accounts.
    """
    async with AsyncSessionLocal() as session:
        accounts = await UserAccountsRepository.get_all_accounts(session)

    user = getattr(request.state, "user", None) or {}
    current_user_email = user.get("email", "")

    return {
        "users": [
            {
                "id": account.id,
                "email": account.email,
                "discord_username": account.discord_username,
                "discord_user_id": account.discord_user_id,
                "role": account.role,
                "role_edited_by": account.role_edited_by,
                "invited_by": account.invited_by,
                "created_at": account.created_at.isoformat() if account.created_at else None,
            }
            for account in accounts
        ],
        "current_user_email": current_user_email,
        "admin_emails": list(ADMIN_EMAILS),
    }


@router.put("/users/{email}/role", dependencies=[Depends(require_admin)])
async def update_user_role(email: str, body: UpdateRoleRequest, request: Request):
    """
    Update a user's role (admin only).

    Args:
        email: The email of the user to update.
        body: Contains the new role.
        request: The FastAPI request object.

    Returns:
        JSON with the updated user info.
    """
    user = getattr(request.state, "user", None) or {}
    current_user_email = user.get("email", "")

    if email == current_user_email:
        raise HTTPException(
            status_code=400,
            detail="You cannot change your own role.",
        )

    if email in ADMIN_EMAILS:
        raise HTTPException(
            status_code=400,
            detail="Cannot change the role of a root admin.",
        )

    valid_roles = tuple(r.value for r in AccountRoles)
    if body.role not in valid_roles:
        raise HTTPException(
            status_code=400,
            detail=f"role must be one of: {', '.join(valid_roles)}",
        )

    async with AsyncSessionLocal() as session:
        updated = await UserAccountsRepository.update_role(
            session, email, body.role, role_edited_by=current_user_email
        )
    if not updated:
        raise HTTPException(status_code=404, detail=f"User '{email}' not found")

    logger.info(f"👤 Admin updated role for '{email}' to '{body.role}'")
    return {"email": updated.email, "role": updated.role}
