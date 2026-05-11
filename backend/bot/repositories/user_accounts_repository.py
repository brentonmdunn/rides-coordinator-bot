"""
User accounts repository.

Data access layer for user account management.
"""

import logging
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from bot.core.enums import AccountRoles
from bot.core.models import UserAccount

logger = logging.getLogger(__name__)


class UserAccountsRepository:
    """Repository for user account CRUD operations."""

    @staticmethod
    async def get_all_accounts(session: AsyncSession) -> list[UserAccount]:
        """
        Get all user accounts, ordered by email.

        Args:
            session: The database session.

        Returns:
            List of all UserAccount records.
        """
        result = await session.execute(select(UserAccount).order_by(UserAccount.email))
        return list(result.scalars().all())

    @staticmethod
    async def get_by_email(session: AsyncSession, email: str) -> UserAccount | None:
        """
        Get a user account by email.

        Args:
            session: The database session.
            email: The email address to look up.

        Returns:
            UserAccount if found, None otherwise.
        """
        result = await session.execute(select(UserAccount).where(UserAccount.email == email))
        return result.scalars().first()

    @staticmethod
    async def create_account(
        session: AsyncSession, email: str, role: AccountRoles = AccountRoles.VIEWER
    ) -> UserAccount:
        """
        Create a new user account.

        Args:
            session: The database session.
            email: The email address for the account.
            role: The role to assign (defaults to viewer).

        Returns:
            The created UserAccount.
        """
        account = UserAccount(email=email, role=role)
        session.add(account)
        await session.commit()
        await session.refresh(account)
        logger.info(f"👤 Created user account for '{email}' with role '{role}'")
        return account

    @staticmethod
    async def get_or_create(
        session: AsyncSession,
        email: str,
        default_role: AccountRoles = AccountRoles.VIEWER,
    ) -> UserAccount:
        """
        Get an existing account or create a new one.

        Args:
            session: The database session.
            email: The email address to look up or create.
            default_role: Role to assign if creating a new account.

        Returns:
            The existing or newly created UserAccount.
        """
        account = await UserAccountsRepository.get_by_email(session, email)
        if account:
            return account
        return await UserAccountsRepository.create_account(session, email, default_role)

    @staticmethod
    async def get_by_discord_user_id(
        session: AsyncSession, discord_user_id: str
    ) -> UserAccount | None:
        """Look up an account by its stable Discord user ID."""
        result = await session.execute(
            select(UserAccount).where(UserAccount.discord_user_id == discord_user_id)
        )
        return result.scalars().first()

    @staticmethod
    async def get_by_discord_username(
        session: AsyncSession, discord_username: str
    ) -> UserAccount | None:
        """Look up any account by Discord username regardless of link status."""
        result = await session.execute(
            select(UserAccount).where(UserAccount.discord_username == discord_username)
        )
        return result.scalars().first()

    @staticmethod
    async def get_unlinked_by_discord_username(
        session: AsyncSession, discord_username: str
    ) -> UserAccount | None:
        """Get an account by Discord username only if it has no discord_user_id yet (unlinked)."""
        result = await session.execute(
            select(UserAccount).where(
                UserAccount.discord_username == discord_username,
                UserAccount.discord_user_id.is_(None),
            )
        )
        return result.scalars().first()

    @staticmethod
    async def get_unlinked_by_email(session: AsyncSession, email: str) -> UserAccount | None:
        """Get an account by email only if it has no discord_user_id yet (unlinked, grandfather path)."""
        result = await session.execute(
            select(UserAccount).where(
                UserAccount.email == email,
                UserAccount.discord_user_id.is_(None),
            )
        )
        return result.scalars().first()

    @staticmethod
    async def link_discord_identity(
        session: AsyncSession,
        account_id: int,
        discord_user_id: str,
        discord_username: str,
        email: str | None,
    ) -> UserAccount | None:
        """Populate Discord identity fields on an existing account after first login."""
        values: dict = {"discord_user_id": discord_user_id, "discord_username": discord_username}
        if email is not None:
            values["email"] = email
        result = await session.execute(
            update(UserAccount)
            .where(UserAccount.id == account_id)
            .values(**values)
            .returning(UserAccount)
        )
        await session.commit()
        return result.scalars().first()

    @staticmethod
    async def create_invited(
        session: AsyncSession,
        discord_username: str,
        role: AccountRoles,
        invited_by: str,
    ) -> UserAccount:
        """Create an invite-only account with no email yet — populated on first login."""
        account = UserAccount(
            email=None,
            discord_username=discord_username,
            role=role,
            invited_by=invited_by,
            invited_at=datetime.utcnow(),
        )
        session.add(account)
        await session.commit()
        await session.refresh(account)
        logger.info(f"👤 Invited '{discord_username}' with role '{role}' (by '{invited_by}')")
        return account

    @staticmethod
    async def delete_by_id(session: AsyncSession, account_id: int) -> bool:
        """Delete a user account by primary key. Returns True if found and deleted."""
        account = await session.get(UserAccount, account_id)
        if not account:
            return False
        await session.delete(account)
        await session.commit()
        return True

    @staticmethod
    async def update_role(
        session: AsyncSession,
        email: str,
        role: AccountRoles,
        role_edited_by: str | None = None,
    ) -> UserAccount | None:
        """
        Update the role of an existing account.

        Args:
            session: The database session.
            email: The email address of the account to update.
            role: The new role to assign.
            role_edited_by: Email of the admin who made the change.

        Returns:
            The updated UserAccount, or None if not found.
        """
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
