"""Service for whois command operations."""

from sqlalchemy.engine import Row
from sqlalchemy.ext.asyncio import AsyncSession

from bot.core.database import AsyncSessionLocal
from bot.repositories.whois_repository import WhoisRepository


class WhoisService:
    """Service for handling whois lookups."""

    @staticmethod
    async def get_whois_data(name: str, session: AsyncSession | None = None) -> str | None:
        """
        Retrieves matching user data from the database and formats it into a display message.

        Args:
            name: The search term (partial name or Discord username) provided by the user.
            session: Optional database session. If None, one is created internally.

        Returns:
            A formatted multi-line string containing the Name and Discord username for all
            matches, separated by a horizontal rule (---). Returns None if no matches are found.
        """
        if session is not None:
            return await WhoisService._get_whois_data(session, name)

        async with AsyncSessionLocal() as session:
            return await WhoisService._get_whois_data(session, name)

    @staticmethod
    async def _get_whois_data(session: AsyncSession, name: str) -> str | None:
        possible_people: list[Row] = await WhoisRepository.fetch_data_by_name(session, name)

        if not possible_people:
            return None

        message: list[str] = []
        for person in possible_people:
            message.append(f"**Name:** {person.name}\n**Discord:** {person.discord_username}")

        return "\n---\n".join(message)
