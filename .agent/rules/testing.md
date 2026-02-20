---
trigger: always_on
---

# Testing Conventions

## Backend (Python)

- Tests live in `backend/tests/`, split into `unit/` and `integration/` directories.
- Run tests: `uv run pytest` (from `backend/`).
- Use `pytest-asyncio` for async test functions.
- Use `pytest-cov` for coverage reporting.

## Available Invoke Tasks

All run from `backend/` with `uv run invoke <task>`:

- `uv run invoke lint` — Run Ruff linter
- `uv run invoke format` — Format code with Ruff
- `uv run invoke fix` — Autofix lint errors
- `uv run invoke all` — Run lint + fix + format
- `uv run invoke test` — Run pytest
- `uv run invoke clean` — Remove dev commands

## Frontend (TypeScript)

- Run linter: `npm run lint` (from `frontend/`).

## Before Committing

- Always run `uv run invoke format` and `uv run invoke lint` after modifying Python code.
- Always run `npm run lint` after modifying frontend code.
