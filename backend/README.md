# Rides Coordinator Bot - Backend

[![Python](https://img.shields.io/badge/python-3.13-blue.svg)](https://www.python.org/downloads/)

The backend is built with **Python 3.13**, using **discord.py** for bot functionality and **FastAPI** for the API layer.

## 🚀 Setup & Installation

### Prerequisites
- Python 3.13+
- [uv](https://docs.astral.sh/uv/) (Recommended for package management)
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

## 🛠️ Development

### Running the Application
To run the bot and API together:

```bash
uv run python main.py
```
*Or if using virtualenv directly:*
```bash
python main.py
```

### Code Quality (Linting & Formatting)
We use `invoke` to manage development tasks.

| Command | Description |
|---------|-------------|
| `uv run invoke lint` | Check code for linting errors (Ruff) |
| `uv run invoke format` | Format code (Ruff) |
| `uv run invoke fix` | Auto-fix linting errors |
| `uv run invoke test` | Run tests (pytest) |
| `uv run invoke all` | Run lint, fix, and format |

## 🧪 Testing

Run the test suite using pytest:

```bash
uv run pytest
```

## 🐳 Docker Deployment

The backend can be deployed via the root Docker configuration.

```bash
# From root directory
docker build -t ride-bot .
```

