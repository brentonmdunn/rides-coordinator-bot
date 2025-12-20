"""Database models.

This module defines the SQLAlchemy models for the application's database tables.
"""

from sqlalchemy import Boolean, Column, Date, Integer, PrimaryKeyConstraint, String

from bot.core.base import Base


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
