"""User accounts service.

Business logic for user account management and role-based access control.
"""

from bot.core.enums import AccountRoles
from bot.repositories.user_accounts_repository import UserAccountsRepository

# Role hierarchy levels (higher = more permissions)
ROLE_LEVELS: dict[str, int] = {
    AccountRoles.VIEWER: 1,
    AccountRoles.RIDE_COORDINATOR: 2,
    AccountRoles.ADMIN: 3,
}


class UserAccountsService:
    """Service for user account operations and role checks."""

    @staticmethod
    async def get_or_create_account(email: str):
        """Get or create a user account with default viewer role.

        Args:
            email: The email address of the user.

        Returns:
            The existing or newly created UserAccount.
        """
        return await UserAccountsRepository.get_or_create(email)

    @staticmethod
    async def has_minimum_role(email: str, minimum_role: AccountRoles) -> bool:
        """Check if a user has at least the specified role level.

        Args:
            email: The email address to check.
            minimum_role: The minimum required role.

        Returns:
            True if the user's role meets or exceeds the minimum.
        """
        account = await UserAccountsRepository.get_by_email(email)
        if not account:
            return False

        user_level = ROLE_LEVELS.get(account.role, 0)
        required_level = ROLE_LEVELS.get(minimum_role, 0)
        return user_level >= required_level
