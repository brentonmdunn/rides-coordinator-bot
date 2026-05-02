"""
Database models.

This module defines the SQLAlchemy models for the application's database tables.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Enum as SQLEnum
from sqlalchemy import func
from sqlalchemy.orm import Mapped, mapped_column

from bot.core.base import Base
from bot.core.enums import AccountRoles, JobName


class DiscordUsers(Base):
    """Model representing a Discord user in the system."""

    __tablename__ = "discord_usernames"

    id: Mapped[int] = mapped_column(primary_key=True, index=True, autoincrement=True)
    discord_username: Mapped[str]
    first_name: Mapped[str]
    last_name: Mapped[str]


class FeatureFlags(Base):
    """Model representing a feature flag."""

    __tablename__ = "feature_flags"

    id: Mapped[int] = mapped_column(primary_key=True, index=True, autoincrement=True)
    feature: Mapped[str] = mapped_column(unique=True)
    enabled: Mapped[bool] = mapped_column(default=False)


class Locations(Base):
    """Model representing a user's location and ride preferences."""

    __tablename__ = "locations"

    id: Mapped[int] = mapped_column(primary_key=True, index=True, autoincrement=True)
    name: Mapped[str]
    discord_username: Mapped[str | None]
    year: Mapped[str | None]
    location: Mapped[str | None]
    driver: Mapped[str | None]


class EventThreads(Base):
    """Model representing a thread associated with an event."""

    __tablename__ = "event_threads"

    message_id: Mapped[str] = mapped_column(primary_key=True)


class NonDiscordRides(Base):
    """Model representing a ride request from a non-Discord user."""

    __tablename__ = "non_discord_rides"

    name: Mapped[str] = mapped_column(primary_key=True)
    date: Mapped[date] = mapped_column(primary_key=True)
    location: Mapped[str | None]


class RideCoverage(Base):
    """Model representing a ride coverage entry."""

    __tablename__ = "ride_coverage"

    discord_username: Mapped[str] = mapped_column(primary_key=True)
    message_id: Mapped[str] = mapped_column(primary_key=True)
    datetime_detected: Mapped[datetime] = mapped_column(server_default=func.now())


class MessageSchedulePause(Base):
    """
    Model representing a pause/delay for a scheduled ask-rides job.

    Each job (friday, sunday, sunday_class) can be independently paused
    either indefinitely or until a specific event date.
    """

    __tablename__ = "message_schedule_pauses"

    id: Mapped[int] = mapped_column(primary_key=True, index=True, autoincrement=True)
    # values_callable stores StrEnum .value (lowercase string) instead of the default .name
    # (uppercase), matching what was written when role was a plain String column.
    job_name: Mapped[JobName] = mapped_column(
        SQLEnum(JobName, values_callable=lambda obj: [e.value for e in obj]), unique=True
    )
    is_paused: Mapped[bool] = mapped_column(default=False)
    resume_after_date: Mapped[date | None]
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())


class UserAccount(Base):
    """Model representing a user account with role-based access."""

    __tablename__ = "user_accounts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    email: Mapped[str | None] = mapped_column(unique=True, index=True)
    # values_callable stores StrEnum .value (lowercase string) instead of the default .name
    # (uppercase), matching what was written when role was a plain String column.
    role: Mapped[AccountRoles] = mapped_column(
        SQLEnum(AccountRoles, values_callable=lambda obj: [e.value for e in obj]),
        default=AccountRoles.VIEWER,
    )
    role_edited_by: Mapped[str | None]
    discord_user_id: Mapped[str | None] = mapped_column(unique=True, index=True)
    discord_username: Mapped[str | None]
    invited_by: Mapped[str | None]
    invited_at: Mapped[datetime | None]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())


class AuthSession(Base):
    """Model representing a server-side auth session."""

    __tablename__ = "auth_sessions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_id_hash: Mapped[str] = mapped_column(unique=True, index=True)
    email: Mapped[str] = mapped_column(index=True)
    csrf_token: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    last_activity_at: Mapped[datetime] = mapped_column(server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(index=True)


class UserPreferences(Base):
    """
    Model representing per-user UI/app preferences.

    Keyed by email (matching user_accounts.email).
    New preference columns can be added here without touching user_accounts.
    """

    __tablename__ = "user_preferences"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(unique=True, index=True)
    show_map_labels: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())
