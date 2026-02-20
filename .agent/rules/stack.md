---
trigger: always_on
---

This project contains both a Discord bot (coded in Python) and a frontend web UI.

Tech stack:
- Discord bot
  - Python
- Backend API
  - Python
  - FastAPI for API
- Frontend
  - React
  - Tailwind CSS
- Database
  - sqlite

Tools:
- Use uv to run python or any python associated libraries. For example, uv run pytest
- Ruff for linting and formatting
- If modifying any python code, ensure that you run `uv run invoke format` and `uv run invoke format`