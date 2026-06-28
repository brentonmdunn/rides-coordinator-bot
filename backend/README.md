# Rides Coordinator Bot - Backend

[![Python](https://img.shields.io/badge/python-3.13-blue.svg)](https://www.python.org/downloads/)

The backend is built with **Python 3.13**, using **discord.py** for bot functionality and **FastAPI** for the API layer.

## Setup & Installation

### Prerequisites
- Python 3.13+
- [uv](https://docs.astral.sh/uv/)
- Docker (optional, for deployment)

### Installation

1. Navigate to the backend directory:
   ```bash
   cd backend
   ```

2. Install dependencies using `uv`:
   ```bash
   uv sync
   ```

3. Configure environment variables:
   ```bash
   cp .env.example .env
   # Edit .env with your Discord tokens and other secrets
   ```

## Development

### Running the Application

```bash
uv run python main.py
```

### Code Quality

| Command | Description |
|---------|-------------|
| `uv run invoke lint` | Check code for linting errors (Ruff) |
| `uv run invoke format` | Format code (Ruff) |
| `uv run invoke fix` | Auto-fix linting errors |
| `uv run invoke test` | Run tests (pytest) |
| `uv run invoke all` | Run lint, fix, and format |
| `uv run ty check` | Type check (ty) |

## Testing

```bash
uv run pytest
```

## Docker Deployment

```bash
docker pull brentonmdunn/ride-bot
```
