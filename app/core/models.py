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
