"""
Service for user-managed pickup locations, travel-time edges, and living mappings.

Owns the unit-of-work for the pickup-locations tables and holds an in-memory
snapshot cache of the full routing graph (locations, edges, mappings, pickup
adjustment). Every mutation invalidates the cache so the next read re-fetches.
"""

import asyncio
import heapq
import logging
from dataclasses import dataclass, field

from rapidfuzz import fuzz, process, utils

from bot.core.database import AsyncSessionLocal
from bot.core.enums import CampusLivingLocations
from bot.core.models import PickupLocation, PickupLocationEdge
from bot.repositories.global_settings_repository import GlobalSettingsRepository
from bot.repositories.pickup_locations_repository import PickupLocationsRepository

logger = logging.getLogger(__name__)

PICKUP_ADJUSTMENT_KEY = "ride_grouping_pickup_adjustment"
DEFAULT_PICKUP_ADJUSTMENT = 1

# Virtual routing-graph nodes for the trip origin/destination (the church).
START_NODE = "START"
END_NODE = "END"

FUZZY_TOKEN_SORT_CUTOFF = 65
FUZZY_PARTIAL_CUTOFF = 60


@dataclass(frozen=True)
class LocationInfo:
    """Plain snapshot of a pickup location row."""

    id: int
    name: str
    latitude: float
    longitude: float
    minutes_from_start: int | None
    minutes_to_end: int | None
    is_active: bool
    is_seeded: bool


@dataclass(frozen=True)
class EdgeInfo:
    """Plain snapshot of a travel-time edge row."""

    id: int
    location_a_id: int
    location_b_id: int
    minutes: int


@dataclass(frozen=True)
class RoutingContext:
    """
    Immutable snapshot of the routing graph used by ride grouping and routes.

    ``graph`` maps node name (location name or START/END) to a list of
    ``(neighbor_name, minutes)`` tuples, covering active locations only.
    """

    locations: tuple[LocationInfo, ...]
    edges: tuple[EdgeInfo, ...]
    living_to_pickup: dict[str, str]
    pickup_adjustment: int
    graph: dict[str, list[tuple[str, int]]] = field(default_factory=dict)

    @property
    def active_names(self) -> list[str]:
        """Names of active pickup locations."""
        return [loc.name for loc in self.locations if loc.is_active]

    def coordinates(self, name: str) -> tuple[float, float] | None:
        """Return (lat, lng) for a location name, or None if unknown."""
        for loc in self.locations:
            if loc.name == name:
                return (loc.latitude, loc.longitude)
        return None

    def map_url(self, name: str) -> str | None:
        """Generate a Google Maps URL for a pickup location name."""
        coords = self.coordinates(name)
        if coords is None:
            return None
        lat, lng = coords
        return f"https://www.google.com/maps?q={lat},{lng}"

    def map_links(self) -> dict[str, str]:
        """Return a dict of active location names to Google Maps URLs."""
        return {name: url for name in self.active_names if (url := self.map_url(name)) is not None}

    def lookup_time(self, start_name: str, end_name: str) -> int:
        """
        Shortest travel time in minutes between two locations (Dijkstra).

        Raises:
            ValueError: If no path exists between the two locations.
        """
        return dijkstra(self.graph, start_name, end_name)

    def fuzzy_match(self, input_loc: str) -> str | None:
        """Fuzzy-match an input string to an active pickup location name."""
        names = self.active_names
        if not names:
            return None

        result = process.extractOne(
            input_loc,
            names,
            scorer=fuzz.token_sort_ratio,
            score_cutoff=FUZZY_TOKEN_SORT_CUTOFF,
            processor=utils.default_process,
        )
        if result:
            return str(result[0])

        result = process.extractOne(
            input_loc,
            names,
            scorer=fuzz.partial_ratio,
            score_cutoff=FUZZY_PARTIAL_CUTOFF,
            processor=utils.default_process,
        )
        if result:
            logger.debug(f"Fallback match: '{input_loc}' -> '{result[0]}' (Score: {result[1]})")
            return str(result[0])

        return None

    def pickup_for_living(self, living_location: str) -> str:
        """
        Return the pickup location name for a living location value.

        Raises:
            ValueError: If the living location has no mapping.
        """
        pickup = self.living_to_pickup.get(living_location)
        if pickup is None:
            raise ValueError(f"No pickup location mapped for living location '{living_location}'")
        return pickup

    def unreachable_names(self) -> list[str]:
        """Active locations with no path to the START or END virtual nodes."""
        return [
            name
            for name in self.active_names
            if not _connected(self.graph, name, START_NODE)
            or not _connected(self.graph, name, END_NODE)
        ]


def dijkstra(graph: dict[str, list[tuple[str, int]]], start: str, end: str) -> int:
    """
    Shortest-path travel time between two nodes of the routing graph.

    Raises:
        ValueError: If no path exists.
    """
    if start == end:
        return 0
    distances: dict[str, float] = {node: float("inf") for node in graph}
    distances[start] = 0
    priority_queue: list[tuple[float, str]] = [(0, start)]

    while priority_queue:
        current_distance, current_node = heapq.heappop(priority_queue)

        if current_distance > distances.get(current_node, float("inf")):
            continue

        if current_node == end:
            return int(current_distance)

        for neighbor, minutes in graph.get(current_node, []):
            distance = current_distance + minutes
            if distance < distances.get(neighbor, float("inf")):
                distances[neighbor] = distance
                heapq.heappush(priority_queue, (distance, neighbor))

    raise ValueError(f"No path found from {start} to {end}")


def _connected(graph: dict[str, list[tuple[str, int]]], start: str, end: str) -> bool:
    """Whether a path exists between two nodes."""
    try:
        dijkstra(graph, start, end)
    except ValueError:
        return False
    return True


def build_graph(
    locations: tuple[LocationInfo, ...], edges: tuple[EdgeInfo, ...]
) -> dict[str, list[tuple[str, int]]]:
    """Build the routing adjacency (incl. START/END) from active locations and edges."""
    active_by_id = {loc.id: loc for loc in locations if loc.is_active}
    graph: dict[str, list[tuple[str, int]]] = {loc.name: [] for loc in active_by_id.values()}
    graph[START_NODE] = []
    graph[END_NODE] = []

    for edge in edges:
        loc_a = active_by_id.get(edge.location_a_id)
        loc_b = active_by_id.get(edge.location_b_id)
        if loc_a is None or loc_b is None:
            continue
        graph[loc_a.name].append((loc_b.name, edge.minutes))
        graph[loc_b.name].append((loc_a.name, edge.minutes))

    for loc in active_by_id.values():
        if loc.minutes_from_start is not None:
            graph[START_NODE].append((loc.name, loc.minutes_from_start))
            graph[loc.name].append((START_NODE, loc.minutes_from_start))
        if loc.minutes_to_end is not None:
            graph[END_NODE].append((loc.name, loc.minutes_to_end))
            graph[loc.name].append((END_NODE, loc.minutes_to_end))

    return graph


class PickupLocationsService:
    """Business logic for pickup locations. Cache is shared across instances."""

    _snapshot: RoutingContext | None = None
    _lock = asyncio.Lock()

    # --- Snapshot / reads ------------------------------------------------

    @classmethod
    def invalidate_cache(cls) -> None:
        """Drop the cached routing snapshot so the next read re-fetches."""
        cls._snapshot = None

    @classmethod
    async def get_routing_context(cls) -> RoutingContext:
        """Return the cached routing snapshot, loading it from the DB if needed."""
        if cls._snapshot is not None:
            return cls._snapshot
        async with cls._lock:
            if cls._snapshot is not None:
                return cls._snapshot
            snapshot = await cls._load_snapshot()
            cls._snapshot = snapshot
            return snapshot

    @classmethod
    def get_routing_context_sync(cls) -> RoutingContext:
        """
        Synchronous snapshot access for non-async callers (e.g. agent tools).

        Must not be called from within a running event loop.
        """
        return asyncio.run(cls.get_routing_context())

    @classmethod
    async def _load_snapshot(cls) -> RoutingContext:
        async with AsyncSessionLocal() as session:
            locations = await PickupLocationsRepository.get_all_locations(session)
            edges = await PickupLocationsRepository.get_all_edges(session)
            mappings = await PickupLocationsRepository.get_all_mappings(session)
            raw_adjustment = await GlobalSettingsRepository.get(session, PICKUP_ADJUSTMENT_KEY)

            location_infos = tuple(cls._to_location_info(loc) for loc in locations)
            edge_infos = tuple(cls._to_edge_info(edge) for edge in edges)
            names_by_id = {loc.id: loc.name for loc in location_infos}
            living_to_pickup = {
                m.living_location: names_by_id[m.pickup_location_id]
                for m in mappings
                if m.pickup_location_id in names_by_id
            }

            try:
                adjustment = int(raw_adjustment) if raw_adjustment is not None else None
            except ValueError:
                logger.warning(f"Invalid {PICKUP_ADJUSTMENT_KEY} value: {raw_adjustment!r}")
                adjustment = None
            if adjustment is None:
                adjustment = DEFAULT_PICKUP_ADJUSTMENT

            logger.debug(
                f"Loaded pickup locations snapshot: {len(location_infos)} locations, "
                f"{len(edge_infos)} edges, {len(living_to_pickup)} mappings"
            )
            return RoutingContext(
                locations=location_infos,
                edges=edge_infos,
                living_to_pickup=living_to_pickup,
                pickup_adjustment=adjustment,
                graph=build_graph(location_infos, edge_infos),
            )

    @staticmethod
    def _to_location_info(loc: PickupLocation) -> LocationInfo:
        return LocationInfo(
            id=loc.id,
            name=loc.name,
            latitude=loc.latitude,
            longitude=loc.longitude,
            minutes_from_start=loc.minutes_from_start,
            minutes_to_end=loc.minutes_to_end,
            is_active=loc.is_active,
            is_seeded=loc.is_seeded,
        )

    @staticmethod
    def _to_edge_info(edge: PickupLocationEdge) -> EdgeInfo:
        return EdgeInfo(
            id=edge.id,
            location_a_id=edge.location_a_id,
            location_b_id=edge.location_b_id,
            minutes=edge.minutes,
        )

    @classmethod
    async def get_all(cls) -> dict:
        """Full management payload for the API: locations, edges, mappings, settings."""
        ctx = await cls.get_routing_context()
        return {
            "locations": [vars(loc) | {} for loc in ctx.locations],
            "edges": [vars(edge) | {} for edge in ctx.edges],
            "living_mappings": [
                {
                    "living_location": living,
                    "pickup_location_id": next(
                        loc.id for loc in ctx.locations if loc.name == pickup
                    ),
                }
                for living, pickup in ctx.living_to_pickup.items()
            ],
            "pickup_adjustment": ctx.pickup_adjustment,
            "unreachable": ctx.unreachable_names(),
        }

    # --- Mutations --------------------------------------------------------

    @classmethod
    async def create_location(
        cls,
        *,
        name: str,
        latitude: float,
        longitude: float,
        minutes_from_start: int | None = None,
        minutes_to_end: int | None = None,
    ) -> LocationInfo:
        """
        Create a pickup location.

        Raises:
            ValueError: If a location with the same name already exists.
        """
        cls.invalidate_cache()
        try:
            async with AsyncSessionLocal() as session:
                existing = await PickupLocationsRepository.get_location_by_name(session, name)
                if existing is not None:
                    raise ValueError(f"A pickup location named '{name}' already exists")
                location = await PickupLocationsRepository.create_location(
                    session,
                    name=name,
                    latitude=latitude,
                    longitude=longitude,
                    minutes_from_start=minutes_from_start,
                    minutes_to_end=minutes_to_end,
                )
                info = cls._to_location_info(location)
                await session.commit()
                logger.info(f"Created pickup location '{name}' (id={info.id})")
                return info
        finally:
            cls.invalidate_cache()

    @classmethod
    async def update_location(cls, location_id: int, **fields) -> LocationInfo | None:
        """
        Update fields on a pickup location. Returns None if the id is unknown.

        Raises:
            ValueError: If renaming to a name that already exists.
        """
        cls.invalidate_cache()
        try:
            async with AsyncSessionLocal() as session:
                location = await PickupLocationsRepository.get_location(session, location_id)
                if location is None:
                    return None
                new_name = fields.get("name")
                if new_name is not None and new_name != location.name:
                    existing = await PickupLocationsRepository.get_location_by_name(
                        session, new_name
                    )
                    if existing is not None:
                        raise ValueError(f"A pickup location named '{new_name}' already exists")
                for key, value in fields.items():
                    setattr(location, key, value)
                info = cls._to_location_info(location)
                await session.commit()
                logger.info(f"Updated pickup location id={location_id}: {sorted(fields)}")
                return info
        finally:
            cls.invalidate_cache()

    @classmethod
    async def soft_delete_location(cls, location_id: int) -> bool:
        """
        Deactivate a pickup location. Returns False if the id is unknown.

        Raises:
            ValueError: If living-location mappings still point at the location.
        """
        cls.invalidate_cache()
        try:
            async with AsyncSessionLocal() as session:
                location = await PickupLocationsRepository.get_location(session, location_id)
                if location is None:
                    return False
                mappings = await PickupLocationsRepository.get_mappings_for_location(
                    session, location_id
                )
                if mappings:
                    living = ", ".join(sorted(m.living_location for m in mappings))
                    raise ValueError(
                        f"Cannot delete '{location.name}': living location(s) still "
                        f"mapped to it: {living}. Remap them first."
                    )
                location.is_active = False
                await session.commit()
                logger.info(f"Deactivated pickup location '{location.name}' (id={location_id})")
                return True
        finally:
            cls.invalidate_cache()

    @classmethod
    async def upsert_edge(cls, location_a_id: int, location_b_id: int, minutes: int) -> EdgeInfo:
        """
        Create or update the travel-time edge between two locations.

        Raises:
            ValueError: On self-edges or unknown/inactive location ids.
        """
        if location_a_id == location_b_id:
            raise ValueError("An edge must connect two different locations")
        a_id, b_id = sorted((location_a_id, location_b_id))
        cls.invalidate_cache()
        try:
            async with AsyncSessionLocal() as session:
                for loc_id in (a_id, b_id):
                    location = await PickupLocationsRepository.get_location(session, loc_id)
                    if location is None or not location.is_active:
                        raise ValueError(f"Unknown or inactive pickup location id {loc_id}")
                edge = await PickupLocationsRepository.get_edge_by_pair(session, a_id, b_id)
                if edge is None:
                    edge = await PickupLocationsRepository.create_edge(session, a_id, b_id, minutes)
                else:
                    edge.minutes = minutes
                info = cls._to_edge_info(edge)
                await session.commit()
                logger.info(f"Upserted edge {a_id}<->{b_id} = {minutes} min")
                return info
        finally:
            cls.invalidate_cache()

    @classmethod
    async def delete_edge(cls, edge_id: int) -> bool:
        """Delete an edge. Returns False if the id is unknown."""
        cls.invalidate_cache()
        try:
            async with AsyncSessionLocal() as session:
                deleted = await PickupLocationsRepository.delete_edge(session, edge_id)
                await session.commit()
                if deleted:
                    logger.info(f"Deleted edge id={edge_id}")
                return deleted
        finally:
            cls.invalidate_cache()

    @classmethod
    async def set_living_mapping(cls, living_location: str, pickup_location_id: int) -> dict:
        """
        Point a living location at a pickup location.

        Raises:
            ValueError: On invalid living location or unknown/inactive pickup id.
        """
        valid_living = {loc.value for loc in CampusLivingLocations}
        if living_location not in valid_living:
            raise ValueError(f"Unknown living location '{living_location}'")
        cls.invalidate_cache()
        try:
            async with AsyncSessionLocal() as session:
                location = await PickupLocationsRepository.get_location(session, pickup_location_id)
                if location is None or not location.is_active:
                    raise ValueError(f"Unknown or inactive pickup location id {pickup_location_id}")
                mapping = await PickupLocationsRepository.upsert_mapping(
                    session, living_location, pickup_location_id
                )
                result = {
                    "living_location": mapping.living_location,
                    "pickup_location_id": mapping.pickup_location_id,
                }
                await session.commit()
                logger.info(f"Mapped living '{living_location}' -> pickup id={pickup_location_id}")
                return result
        finally:
            cls.invalidate_cache()

    @classmethod
    async def set_pickup_adjustment(cls, value: int) -> int:
        """
        Set the per-stop pickup time adjustment (minutes).

        Raises:
            ValueError: If value is negative.
        """
        if value < 0:
            raise ValueError("Pickup adjustment must be >= 0")
        cls.invalidate_cache()
        try:
            async with AsyncSessionLocal() as session:
                await GlobalSettingsRepository.set(session, PICKUP_ADJUSTMENT_KEY, str(value))
                await session.commit()
                logger.info(f"Set pickup adjustment to {value}")
                return value
        finally:
            cls.invalidate_cache()
