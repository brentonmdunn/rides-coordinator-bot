# Documentation Hub

Welcome to the central documentation hub for the Rides Coordinator Bot project.

## Project Overview

The project consists of three main components:

1. **Discord Bot (Python):** Handles slash commands, reactions, and direct engagement with Discord users.
2. **Backend API (FastAPI):** Business logic, database access, and the web dashboard API. Runs alongside the bot in a single process.
3. **Frontend Dashboard (React):** Admin SPA for visualizing pickup coverage, coordinating rides, managing users, and controlling the bot's scheduled messages.

---

## Documentation Index

| Document | Description |
|----------|-------------|
| [setup.md](setup.md) | Local development setup, environment variables, running tests |
| [api-reference.md](api-reference.md) | All HTTP API endpoints with request/response shapes |
| [bot-commands.md](bot-commands.md) | All Discord slash commands |
| [scheduler.md](scheduler.md) | Scheduled jobs (APScheduler), how they work, how to pause them |
| [database-schema.md](database-schema.md) | All database tables and their columns |
| [feature-flags.md](feature-flags.md) | Feature flag reference and management |
| [auth.md](auth.md) | Authentication — Discord OAuth flow, roles, sessions, invites |
| [deployment.md](deployment.md) | Docker build, image promotion, environment configuration |
| [CI_CD.md](CI_CD.md) | CI/CD image promotion strategy |

---

## Quick links

- **Contributing:** See `CONTRIBUTING.md` at the repo root for branching, PR, and linting requirements.
- **Frontend env config:** `frontend/ENV_CONFIG.md` explains `VITE_API_URL` and how dev vs. prod API calls work.
- **AI assistant guide:** `CLAUDE.md` at the repo root contains project conventions for AI coding assistants — not end-user documentation.
