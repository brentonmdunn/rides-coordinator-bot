# Greenfield architecture review

The existing Python/FastAPI/discord.py backend, React/Vite dashboard, and modular
monolith are appropriate for this project. Starting fresh, the main changes would
be to data ownership and workflow execution.

## 1. Make rides explicit database entities

Store ride events, people, signups, driver offers, and assignments with stable
identifiers. Discord announcements reference events, and reactions update signups.
The dashboard reads recorded ride state without requiring a live Discord client.
Reconcile external reactions after interruptions rather than interpreting message
text every time a coordinator requests ride data.

Reuse the existing pickup-info roster for registered people. Discord user IDs are
identity keys; usernames and display names are presentation attributes. Preserve
unregistered riders without inventing roster entries or matching people by name.

### Implementation stages

1. Persist dated events and announcement mappings; ingest reaction state by stable
   user ID; expose database-only event/signup reads; provide an explicit import
   and reconciliation path for existing announcements.
2. Reconcile automatically after gateway interruptions, handle message/reaction
   clearing, and move existing dashboard/pickup reads to the new model. Surface
   snapshot freshness so stored state is not mistaken for guaranteed live state.
3. Unify non-Discord requests and custom requests with signups, then model driver
   offers and assignments. Define pickup/return choices explicitly, including
   customized reaction semantics, before switching grouping consumers.

## 2. Use deterministic grouping

Start with a constrained heuristic; introduce a solver if the requirements warrant
it. Validate that every rider appears exactly once, each vehicle respects its
capacity, and all stops are valid. An LLM can interpret free-text preferences or
explain a plan without owning assignment correctness.

## 3. Give application operations clear boundaries

HTTP routes and Discord commands call the same application operations with plain
data. Operations own transactions; repositories query and write without committing
independently. Discord replies, embeds, and dashboard formatting live at the
interface boundaries. External effects need explicit retries and compensation.

## 4. Make background work recoverable

Keep APScheduler, adding a durable record of each logical job run, attempts,
status, and external message IDs. Reconcile overdue work on startup and prevent
duplicate effects. A small database-backed delivery table is sufficient initially.

## 5. Return structured plans and generate API types

Return cars, passengers, stops, and times rather than formatted grouping strings.
Render that data separately for Discord, the dashboard, and clipboard output.
Declare public request/response contracts in FastAPI and generate TypeScript
contracts from OpenAPI.

## What to retain

- Python, FastAPI, discord.py, SQLAlchemy, and Alembic.
- React, Vite, TanStack Query, and same-origin hosting.
- One codebase/deployment with explicit bot and scheduler ownership.
- SQLite for the current single-instance operation; disposable caching.
- Per-bot package boundaries and the import-boundary checks.

Independent availability requirements, write contention, or multiple replicas
would justify separate processes and PostgreSQL. Those changes are not prerequisites
for making ride workflows database-owned.
