"""User accounts repository.

Data access layer for user account management.
"""

from sqlalchemy import select, update

from bot.core.database import AsyncSessionLocal
from bot.core.enums import AccountRoles
from bot.core.logger import logger
from bot.core.models import UserAccount


class UserAccountsRepository:
    """Repository for user account CRUD operations."""

    @staticmethod
    async def get_all_accounts() -> list[UserAccount]:
        """Get all user accounts, ordered by email.

        Returns:
            List of all UserAccount records.
        """
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(UserAccount).order_by(UserAccount.email))
            return list(result.scalars().all())

    @staticmethod
    async def get_by_email(email: str) -> UserAccount | None:
        """Get a user account by email.

        Args:
            email: The email address to look up.

        Returns:
            UserAccount if found, None otherwise.
        """
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(UserAccount).where(UserAccount.email == email))
            return result.scalars().first()

    @staticmethod
    async def create_account(email: str, role: AccountRoles = AccountRoles.VIEWER) -> UserAccount:
        """Create a new user account.

        Args:
            email: The email address for the account.
            role: The role to assign (defaults to viewer).

        Returns:
            The created UserAccount.
        """
        async with AsyncSessionLocal() as session:
            account = UserAccount(email=email, role=role)
            session.add(account)
            await session.commit()
            await session.refresh(account)
            logger.info(f"👤 Created user account for '{email}' with role '{role}'")
            return account

    @staticmethod
    async def get_or_create(
        email: str, default_role: AccountRoles = AccountRoles.VIEWER
    ) -> UserAccount:
        """Get an existing account or create a new one.

        Args:
            email: The email address to look up or create.
            default_role: Role to assign if creating a new account.

        Returns:
            The existing or newly created UserAccount.
        """
        account = await UserAccountsRepository.get_by_email(email)
        if account:
            return account
        return await UserAccountsRepository.create_account(email, default_role)

    @staticmethod
    async def update_role(
        email: str, role: AccountRoles, role_edited_by: str | None = None
    ) -> UserAccount | None:
        """Update the role of an existing account.

        Args:
            email: The email address of the account to update.
            role: The new role to assign.
            role_edited_by: Email of the admin who made the change.

        Returns:
            The updated UserAccount, or None if not found.
        """
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                update(UserAccount)
                .where(UserAccount.email == email)
                .values(role=role, role_edited_by=role_edited_by)
                .returning(UserAccount)
            )
            await session.commit()
            updated = result.scalars().first()
            if updated:
                logger.info(f"👤 Updated role for '{email}' to '{role}' (by '{role_edited_by}')")
            return updated
