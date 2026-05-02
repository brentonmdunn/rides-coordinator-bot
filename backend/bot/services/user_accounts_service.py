"""
User accounts service.

Business logic for user account management and role-based access control.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from bot.core.database import AsyncSessionLocal
from bot.core.enums import AccountRoles
from bot.core.models import UserAccount
from bot.repositories.user_accounts_repository import UserAccountsRepository

ROLE_LEVELS: dict[str, int] = {
    AccountRoles.VIEWER: 1,
    AccountRoles.RIDE_COORDINATOR: 2,
    AccountRoles.ADMIN: 3,
}


class UserAccountsService:
    """Service for user account operations and role checks."""

    @staticmethod
    async def get_or_create_account(email: str, session: AsyncSession | None = None):
        """
        Get or create a user account with default viewer role.

        Args:
            email: The email address of the user.
            session: Optional database session. If None, one is created internally.

        Returns:
            The existing or newly created UserAccount.
        """
        if session is not None:
            return await UserAccountsRepository.get_or_create(session, email)

        async with AsyncSessionLocal() as session:
            return await UserAccountsRepository.get_or_create(session, email)

    @staticmethod
    async def get_account(email: str) -> UserAccount | None:
        """Get an existing account by email without creating one."""
        async with AsyncSessionLocal() as session:
            return await UserAccountsRepository.get_by_email(session, email)

    @staticmethod
    async def invite(
        discord_username: str,
        role: AccountRoles,
        invited_by: str,
    ) -> UserAccount | None:
        """Create an invite record. Returns None if the username already has an account."""
        async with AsyncSessionLocal() as session:
            existing = await UserAccountsRepository.get_by_discord_username(
                session, discord_username
            )
            if existing:
                return None
            return await UserAccountsRepository.create_invited(
                session, discord_username, role, invited_by
            )

    @staticmethod
    async def revoke(account_id: int) -> bool:
        """Delete a user account / revoke an invite."""
        async with AsyncSessionLocal() as session:
            return await UserAccountsRepository.delete_by_id(session, account_id)

    @staticmethod
    async def has_minimum_role(
        email: str, minimum_role: AccountRoles, session: AsyncSession | None = None
    ) -> bool:
        """
        Check if a user has at least the specified role level.

        Args:
            email: The email address to check.
            minimum_role: The minimum required role.
            session: Optional database session. If None, one is created internally.

        Returns:
            True if the user's role meets or exceeds the minimum.
        """
        if session is not None:
            account = await UserAccountsRepository.get_by_email(session, email)
        else:
            async with AsyncSessionLocal() as session:
                account = await UserAccountsRepository.get_by_email(session, email)

        if not account:
            return False

        user_level = ROLE_LEVELS.get(account.role, 0)
        required_level = ROLE_LEVELS.get(minimum_role, 0)
        return user_level >= required_level
