"""Database models.

This module defines the SQLAlchemy models for the application's database tables.
"""

import datetime

from sqlalchemy import Boolean, Column, Date, DateTime, Integer, PrimaryKeyConstraint, String, func

from bot.core.base import Base
from bot.core.enums import AccountRoles


class DiscordUsers(Base):
    """Model representing a Discord user in the system."""

    __tablename__ = "discord_usernames"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    discord_username = Column(String, nullable=False)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)


class FeatureFlags(Base):
    """Model representing a feature flag."""

    __tablename__ = "feature_flags"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    feature = Column(String, nullable=False, unique=True)
    enabled = Column(Boolean, nullable=False, default=False)


class Locations(Base):
    """Model representing a user's location and ride preferences."""

    __tablename__ = "locations"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String, nullable=False)
    discord_username = Column(String)
    year = Column(String)
    location = Column(String)
    driver = Column(String)


class EventThreads(Base):
    """Model representing a thread associated with an event."""

    __tablename__ = "event_threads"
    message_id = Column(String, primary_key=True)


class NonDiscordRides(Base):
    """Model representing a ride request from a non-Discord user."""

    __tablename__ = "non_discord_rides"
    __table_args__ = (PrimaryKeyConstraint("name", "date"),)
    name = Column(String, nullable=False)
    date = Column(Date, nullable=False)
    location = Column(String)


class RideCoverage(Base):
    """Model representing a ride coverage entry."""

    __tablename__ = "ride_coverage"
    __table_args__ = (PrimaryKeyConstraint("discord_username", "message_id"),)
    discord_username = Column(String, nullable=False)
    datetime_detected = Column(DateTime, nullable=False, default=datetime.datetime.now())
    message_id = Column(String, nullable=False)


class MessageSchedulePause(Base):
    """Model representing a pause/delay for a scheduled ask-rides job.

    Each job (friday, sunday, sunday_class) can be independently paused
    either indefinitely or until a specific event date.
    """

    __tablename__ = "message_schedule_pauses"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    job_name = Column(String, nullable=False, unique=True)
    is_paused = Column(Boolean, nullable=False, default=False)
    resume_after_date = Column(Date, nullable=True)
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())


class UserAccount(Base):
    """Model representing a user account with role-based access."""

    __tablename__ = "user_accounts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String, nullable=False, unique=True, index=True)
    role = Column(String, nullable=False, default=AccountRoles.VIEWER)
    role_edited_by = Column(String, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
