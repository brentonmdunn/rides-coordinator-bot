# DESIGN: User-Managed Pickup Locations

Make pickup location names, GPS coordinates, travel times, the living→pickup mapping, and the
pickup-time adjustment constant editable from the web UI instead of hardcoded in Python.

## Decisions (confirmed with owner)

| Question | Decision |
|---|---|
| Scope | Pickup locations (name/coords), travel-time edges, AND living→pickup mapping become DB-backed. `CampusLivingLocations` stays an enum. |
| Travel-time model | Keep the sparse **edge graph** + Dijkstra. Users edit edges (pairs + minutes). START/END become per-location fields. |
| Deletion | **Soft delete** (`is_active` flag). Blocked while a living-location mapping points at the location. Seeded defaults are deletable. |
| UI & access | New dedicated page, gated by `require_ride_coordinator`. |
| Pickup constant | `RIDE_GROUPING_PICKUP_ADJUSTMENT` moves to the existing `global_settings` key-value table. |
| Travel-time source | **100% user-entered.** No routing-engine integration (OSRM/ORS/Google) — current values are hand-tuned for campus realities (loops, stop points, load time), so no auto-suggested times anywhere. |

## Current hardcoded state (inventory)

| What | Where | Notes |
|---|---|---|
| Location names | `PickupLocations` enum, `bot/core/enums.py:134` | `REVELLE` intentionally shares the string `"Eighth basketball courts"` with `EIGHTH` |
| GPS coordinates | `MAP_LOCATIONS` in `bot/utils/constants.py:37` | 12 locations; also feeds `get_map_url()` / `get_map_links()` |
| Travel times | `LOCATIONS_MATRIX` in `bot/utils/locations.py:11` | Directed adjacency list, symmetric for real locations; virtual `START`/`END` nodes model trips from/to the destination (church). Dijkstra (`lookup_time`) fills unconnected pairs. |
| Living→pickup mapping | `LIVING_TO_PICKUP` (approx name) in `bot/services/group_rides_service.py:44` | e.g. Revelle→Eighth, PCE/PCW→Innovation |
| Pickup constant | `RIDE_GROUPING_PICKUP_ADJUSTMENT = 1` in `bot/utils/constants.py:113` | Minutes added per stop in `calculate_pickup_time()` |

Consumers that must switch to DB reads: `ride_grouping.py` (`lookup_time`, `get_map_url`),
`group_rides_service.py` (mapping + `LOCATIONS_MATRIX` import), `route_service.py` (fuzzy match
against enum values), `api/routes/route_builder.py` (`PickupLocations` iteration + `MAP_LOCATIONS`),
`bot/core/schemas.py` (`LocationQuery` typed as `PickupLocations`).

## Database schema (Alembic migration)

> ⚠️ A `locations` table already exists (people's ride preferences), so new tables use the
> `pickup_locations` prefix.

```
pickup_locations
  id                 INTEGER PK AUTOINCREMENT
  name               TEXT NOT NULL UNIQUE          -- e.g. "Muir tennis courts"
  latitude           FLOAT NOT NULL
  longitude          FLOAT NOT NULL
  minutes_from_start INTEGER NULL                  -- replaces START→loc edges (church → first pickup)
  minutes_to_end     INTEGER NULL                  -- replaces loc→END edges (last pickup → church)
  is_active          BOOLEAN NOT NULL DEFAULT 1    -- soft delete
  is_seeded          BOOLEAN NOT NULL DEFAULT 0    -- provenance only; seeded rows are still deletable
  created_at / updated_at (server defaults, onupdate)

pickup_location_edges                              -- undirected; store with location_a_id < location_b_id
  id             INTEGER PK AUTOINCREMENT
  location_a_id  INTEGER NOT NULL FK pickup_locations.id ON DELETE CASCADE
  location_b_id  INTEGER NOT NULL FK pickup_locations.id ON DELETE CASCADE
  minutes        INTEGER NOT NULL CHECK (minutes > 0)
  UNIQUE (location_a_id, location_b_id)

living_location_pickups
  living_location     TEXT PK                      -- value of CampusLivingLocations enum
  pickup_location_id  INTEGER NOT NULL FK pickup_locations.id
```

- Pickup constant: `global_settings` key `ride_grouping_pickup_adjustment` (string int, default `"1"`).
- The current matrix is symmetric for real locations, so undirected edges lose nothing; the only
  asymmetry (START vs END times) is captured by the two per-location columns
  (`from_start`: Innovation/Eighth/Rita/Pepper Canyon Loop = 10; `to_end`: Innovation/Seventh = 20).

### Seeding (requirement 3)

The same Alembic migration that creates the tables also seeds them, using **frozen literal data**
copied from today's constants (never importing live code into a migration):

1. 12 `pickup_locations` rows from `MAP_LOCATIONS` (+ `minutes_from_start` / `minutes_to_end` from
   the START/END edges), `is_seeded = 1`.
2. `pickup_location_edges` rows from the deduplicated symmetric pairs of `LOCATIONS_MATRIX`.
3. `living_location_pickups` rows from the hardcoded mapping — including Revelle→Eighth and
   PCE/PCW→Innovation, which replaces the enum's duplicate-string hack cleanly.
4. `global_settings` upsert for the pickup adjustment.

Because seeding lives in the migration, a fresh DB and an existing prod DB both end up identical,
and `entrypoint.sh`'s pre-migration backup covers rollback.

## Backend changes

### New layers (follows Cog/API → Service → Repository rule)

- `bot/repositories/pickup_locations_repository.py` — static CRUD for all three tables.
- `bot/services/pickup_locations_service.py` — owns sessions, business rules, and an **in-memory
  cache** of the full location graph (locations + edges + mapping + constant). Cache is updated
  before commit and popped on failure per the reliability rules; every mutation invalidates it.
  Reads are hot-path (every ride-grouping run), so this matters.

### Refactors

- `lookup_time()` moves into the service: builds the Dijkstra adjacency from cached DB edges +
  `minutes_from_start`/`minutes_to_end`, keyed by location **id** internally, name at the edges of
  the system. `LocationQuery` in `schemas.py` becomes `str`-typed.
- `group_rides_service.py`: living→pickup lookup and matrix come from the service; fuzzy matching
  (`get_pickup_location_fuzzy`) matches against active DB names instead of enum values.
- `get_map_url` / `get_map_links`: take a location row / name, read coords from the service.
- `api/routes/route_builder.py`: iterate active DB locations instead of the enum.
- `PickupLocations` enum: deleted at the end of the refactor (its data lives frozen in the
  migration). `CampusLivingLocations` remains.
- Unreachable-pair behavior: `lookup_time` currently raises `ValueError`; keep that, but the API
  exposes a connectivity check so the UI can warn *before* Sunday morning breaks (see below).

### API routes — `api/routes/pickup_locations.py`, all `require_ride_coordinator`

| Method & path | Purpose |
|---|---|
| `GET /api/pickup-locations` | Everything in one payload: locations (incl. inactive), edges, living mappings, pickup constant, and a computed `unreachable: [names]` connectivity warning |
| `POST /api/pickup-locations` | Create (name, lat, lng, optional start/end minutes). 409 on duplicate active name |
| `PATCH /api/pickup-locations/{id}` | Edit name/coords/start-end minutes/`is_active` (reactivation goes through here too) |
| `DELETE /api/pickup-locations/{id}` | Soft delete. **409** if a living mapping references it (response says which, so the UI can prompt remapping) |
| `PUT /api/pickup-locations/edges` | Upsert edge `{location_a_id, location_b_id, minutes}` (pair normalized server-side) |
| `DELETE /api/pickup-locations/edges/{id}` | Remove edge |
| `PUT /api/pickup-locations/living-mappings/{living_location}` | Point a living location at a pickup location (validates enum membership + active target) |
| `PUT /api/pickup-locations/settings/pickup-adjustment` | Update the constant (int ≥ 0) |

Validation: lat ∈ [-90, 90], lng ∈ [-180, 180], minutes > 0, non-empty trimmed name.

## Frontend — new `Locations` page

New route `/locations` (`src/pages/Locations.tsx`), linked from the admin/coordinator nav, guarded
the same way other coordinator pages are. react-query for all data (`['pickup-locations']` query
key, invalidated on every mutation).

Layout: **map on top, three collapsible sections below** (Locations, Travel times, Settings).

### Map visualization (requirement 5 — yes, this works)

Leaflet + OpenStreetMap tiles are **already in the project** (`MapConstants.ts`, `MapShared.tsx`,
RouteBuilder), so the stretch goal is cheap:

- One `L.marker` per active location (inactive ones hidden, or shown grayed via a toggle).
- One `L.polyline` per edge, with the minute value rendered at the midpoint using a **permanent
  tooltip** (`polyline.bindTooltip(minutes, { permanent: true, direction: 'center' })`) — this is
  the standard Leaflet way to put a number on a line; no plugin needed.
- Interactions:
  - Click a marker → popup with name/coords, Edit / Deactivate buttons.
  - "Add location" mode → click the map to drop a pin, form pre-filled with clicked lat/lng
    (much better than typing coordinates).
  - "Add edge" mode → click two markers in sequence → minutes prompt → `PUT` edge.
  - Click an edge's number label → inline edit or delete the edge.
- Locations with no path to START/END get a warning badge (from the API's `unreachable` field) and
  a red marker, since ride grouping would crash on them.

### Locations section

Table of all locations: name, lat/lng (click row → map pans there), from-start / to-end minutes,
active toggle, delete. Deleting a mapped location surfaces the 409 as "Remap Revelle first."
Inactive locations shown collapsed with a Reactivate button.

### Travel times section

Edge list (`A ↔ B — n min`) with inline edit/delete and an add-edge form (two location dropdowns +
minutes) as the non-map alternative for the same operations.

### Settings section

- Pickup adjustment constant (number input + save) with helper text explaining it's added per stop.
- Living→pickup mapping: one dropdown per `CampusLivingLocations` value, options = active pickup
  locations.

## Edge cases & safeguards

- **Deactivating a location referenced by edges**: allowed; edges stay in the DB but are excluded
  from the routing graph while inactive (reactivation restores them).
- **Graph connectivity**: computed server-side on every `GET`; UI warns loudly. `lookup_time` still
  raises on an unreachable pair, and ride-grouping's existing error path reports it to Discord.
- **Renames**: historical ride data stores location strings; renames don't rewrite history (same as
  today). The fuzzy matcher absorbs most drift.
- **Concurrent edits**: last-write-wins is fine at this scale; react-query refetch keeps clients
  converged.
- **Cache**: mutation path = write cache → commit → (on exception) pop cache, per CLAUDE.md.

## Implementation phases

1. **Schema + seed** — models, Alembic migration with frozen seed data, repository, service +
   cache, unit tests for Dijkstra-from-DB parity with the old hardcoded outputs (golden test:
   every pair's `lookup_time` result must match pre/post refactor).
2. **Backend cutover** — refactor the five consumer sites to the service; delete
   `MAP_LOCATIONS`, `LOCATIONS_MATRIX`, `RIDE_GROUPING_PICKUP_ADJUSTMENT`, and finally the
   `PickupLocations` enum. `uv run pytest`, `invoke lint/format`, `ty check`.
3. **API routes** — new router + tests (auth, validation, 409 paths, connectivity field).
4. **Frontend page** — tables/forms first (full functionality without the map), then the map layer
   (markers → polylines+tooltips → click-to-add interactions).
5. **Verify** — run the bot locally, exercise `/group_rides` end-to-end against seeded DB data,
   confirm identical output to the hardcoded version.
