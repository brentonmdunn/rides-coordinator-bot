from sqlalchemy import Boolean, Column, Integer, String

from app.core.base import Base


class DiscordUsers(Base):
    __tablename__ = "discord_usernames"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    discord_username = Column(String, nullable=False)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)


class FeatureFlags(Base):
    __tablename__ = "feature_flags"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    feature = Column(String, nullable=False, unique=True)
    enabled = Column(Boolean, nullable=False, default=False)


class Locations(Base):
    __tablename__ = "locations"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String, nullable=False)
    discord_username = Column(String)
    year = Column(String)
    location = Column(String)
    driver = Column(String)


class EventThreads(Base):
    __tablename__ = "event_threads"
    message_id = Column(String, primary_key=True)
