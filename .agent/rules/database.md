---
trigger: always_on
---

# Database Conventions

## Stack

- **SQLite** via **aiosqlite** (async driver) + **SQLAlchemy** (async ORM).
- Database file stored in `backend/db/`.

## Migrations

- Managed by **Alembic** (config: `backend/alembic.ini`, migrations dir: `backend/alembic/`).
- Generate a new migration: `uv run alembic revision --autogenerate -m "description"`
- Apply migrations: `uv run alembic upgrade head`

## Data Access Pattern

- **Repositories** (`bot/repositories/`): All database queries go here. Each repository file focuses on one domain (e.g., `locations_repository.py`, `feature_flags_repository.py`).
- **Services** (`bot/services/`): Call repositories — never write raw SQL in cogs or services.
- Cogs and API routes should call services, not repositories directly.
