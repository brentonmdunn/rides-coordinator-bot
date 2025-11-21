"""Service for whois command operations."""
from sqlalchemy.engine import Row

from app.core.database import AsyncSessionLocal
from app.repositories.whois_repo import WhoisRepo


class WhoisService:
    """Service for handling whois lookups."""
    @staticmethod
    async def get_whois_data(name: str) -> str | None:
        """Retrieves matching user data from the database and formats it into a display message.

        This method handles opening and closing the database session, calls the repository
        to fetch data, and transforms the resulting rows into a readable string.

        Args:
            name: The search term (partial name or Discord username) provided by the user.

        Returns:
            A formatted multi-line string containing the Name and Discord username for all
            matches, separated by a horizontal rule (---). Returns None if no matches are found.
        """
        async with AsyncSessionLocal() as session:
            possible_people: list[Row] = await WhoisRepo.fetch_data_by_name(session, name)

        if not possible_people:
            return None

        message: list[str] = []
        for person in possible_people:
            message.append(f"**Name:** {person.name}\n**Discord:** {person.discord_username}")

        return "\n---\n".join(message)
