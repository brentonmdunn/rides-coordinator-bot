"""
User Info API Endpoint

Returns the current authenticated user's information and role.
Includes a local-only role switcher for development testing.
"""

import os

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from bot.core.enums import AccountRoles
from bot.repositories.user_accounts_repository import UserAccountsRepository
from bot.services.user_accounts_service import UserAccountsService

router = APIRouter()

APP_ENV = os.getenv("APP_ENV", "local")


@router.get("/api/me")
async def get_current_user(request: Request):
    """Return the current authenticated user's email and role.

    Auto-creates the account with default viewer role if not found.

    Returns:
        JSON with user email, role, and environment info
    """
    user = getattr(request.state, "user", None) or {}
    email = user.get("email", "")

    if not email:
        return {"email": "", "role": AccountRoles.VIEWER, "is_local": APP_ENV == "local"}

    account = await UserAccountsService.get_or_create_account(email)
    return {"email": email, "role": account.role, "is_local": APP_ENV == "local"}


class RoleSwitchRequest(BaseModel):
    """Request model for switching the dev user's role."""

    role: str


@router.put("/api/me/role")
async def switch_role(request: Request, body: RoleSwitchRequest):
    """Switch the current user's role (local development only).

    Args:
        body: Contains the new role to switch to.

    Returns:
        JSON with the updated role.
    """
    if APP_ENV != "local":
        raise HTTPException(status_code=403, detail="Role switching is only available locally")

    valid_roles = tuple(r.value for r in AccountRoles)
    if body.role not in valid_roles:
        raise HTTPException(
            status_code=400,
            detail=f"role must be one of: {', '.join(valid_roles)}",
        )

    user = getattr(request.state, "user", None) or {}
    email = user.get("email", "")
    if not email:
        raise HTTPException(status_code=401, detail="Unauthorized")

    updated = await UserAccountsRepository.update_role(email, body.role)
    if not updated:
        raise HTTPException(status_code=404, detail="Account not found")

    return {"email": email, "role": updated.role}
