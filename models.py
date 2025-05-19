from sqlalchemy import Column, Integer, String

from database import Base


class DiscordUsers(Base):
    __tablename__ = "discord_usernames"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    discord_username = Column(String, nullable=False)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
