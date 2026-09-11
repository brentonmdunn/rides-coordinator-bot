"""Repository for pickup location, travel-time edge, and living-location mapping data."""

import logging

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.core.models import LivingLocationPickup, PickupLocation, PickupLocationEdge

logger = logging.getLogger(__name__)


class PickupLocationsRepository:
    """Handles database operations for pickup locations and their routing graph."""

    # --- Locations -----------------------------------------------------

    @staticmethod
    async def get_all_locations(session: AsyncSession) -> list[PickupLocation]:
        """Return all pickup locations (active and inactive)."""
        result = await session.execute(select(PickupLocation).order_by(PickupLocation.name))
        return list(result.scalars().all())

    @staticmethod
    async def get_location(session: AsyncSession, location_id: int) -> PickupLocation | None:
        """Return a pickup location by id, or None."""
        result = await session.execute(
            select(PickupLocation).where(PickupLocation.id == location_id)
        )
        return result.scalars().one_or_none()

    @staticmethod
    async def get_location_by_name(session: AsyncSession, name: str) -> PickupLocation | None:
        """Return a pickup location by exact name, or None."""
        result = await session.execute(select(PickupLocation).where(PickupLocation.name == name))
        return result.scalars().one_or_none()

    @staticmethod
    async def create_location(
        session: AsyncSession,
        *,
        name: str,
        latitude: float,
        longitude: float,
        minutes_from_start: int | None = None,
        minutes_to_end: int | None = None,
    ) -> PickupLocation:
        """Create and return a new pickup location."""
        location = PickupLocation(
            name=name,
            latitude=latitude,
            longitude=longitude,
            minutes_from_start=minutes_from_start,
            minutes_to_end=minutes_to_end,
        )
        session.add(location)
        await session.flush()
        return location

    # --- Edges ---------------------------------------------------------

    @staticmethod
    async def get_all_edges(session: AsyncSession) -> list[PickupLocationEdge]:
        """Return all travel-time edges."""
        result = await session.execute(select(PickupLocationEdge))
        return list(result.scalars().all())

    @staticmethod
    async def get_edge(session: AsyncSession, edge_id: int) -> PickupLocationEdge | None:
        """Return an edge by id, or None."""
        result = await session.execute(
            select(PickupLocationEdge).where(PickupLocationEdge.id == edge_id)
        )
        return result.scalars().one_or_none()

    @staticmethod
    async def get_edge_by_pair(
        session: AsyncSession, location_a_id: int, location_b_id: int
    ) -> PickupLocationEdge | None:
        """Return the edge for a normalized (a < b) location pair, or None."""
        result = await session.execute(
            select(PickupLocationEdge).where(
                PickupLocationEdge.location_a_id == location_a_id,
                PickupLocationEdge.location_b_id == location_b_id,
            )
        )
        return result.scalars().one_or_none()

    @staticmethod
    async def create_edge(
        session: AsyncSession, location_a_id: int, location_b_id: int, minutes: int
    ) -> PickupLocationEdge:
        """Create and return a new edge."""
        edge = PickupLocationEdge(
            location_a_id=location_a_id, location_b_id=location_b_id, minutes=minutes
        )
        session.add(edge)
        await session.flush()
        return edge

    @staticmethod
    async def delete_edge(session: AsyncSession, edge_id: int) -> bool:
        """Delete an edge by id. Returns True if a row was deleted."""
        result = await session.execute(
            delete(PickupLocationEdge).where(PickupLocationEdge.id == edge_id)
        )
        return result.rowcount > 0

    # --- Living-location mappings ---------------------------------------

    @staticmethod
    async def get_all_mappings(session: AsyncSession) -> list[LivingLocationPickup]:
        """Return all living-location → pickup-location mappings."""
        result = await session.execute(select(LivingLocationPickup))
        return list(result.scalars().all())

    @staticmethod
    async def get_mappings_for_location(
        session: AsyncSession, location_id: int
    ) -> list[LivingLocationPickup]:
        """Return mappings that point at the given pickup location."""
        result = await session.execute(
            select(LivingLocationPickup).where(
                LivingLocationPickup.pickup_location_id == location_id
            )
        )
        return list(result.scalars().all())

    @staticmethod
    async def upsert_mapping(
        session: AsyncSession, living_location: str, pickup_location_id: int
    ) -> LivingLocationPickup:
        """Create or update the mapping for a living location."""
        result = await session.execute(
            select(LivingLocationPickup).where(
                LivingLocationPickup.living_location == living_location
            )
        )
        mapping = result.scalars().one_or_none()
        if mapping is None:
            mapping = LivingLocationPickup(
                living_location=living_location, pickup_location_id=pickup_location_id
            )
            session.add(mapping)
        else:
            mapping.pickup_location_id = pickup_location_id
        await session.flush()
        return mapping
