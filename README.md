# Rides Coordinator Bot

[![Python](https://img.shields.io/badge/python-3.13-blue.svg)](https://www.python.org/downloads/)
[![Docker](https://img.shields.io/badge/Docker-RideBot-blue?logo=docker)](https://hub.docker.com/r/brentonmdunn/ride-bot)

This is a Discord bot that helps coordinate ride pickups.

---

## 🚀 Installation

Clone the repository and move into the folder:

```bash
git clone https://github.com/brentonmdunn/rides-coordinator-bot
cd rides-coordinator-bot
```

Create and activate a virtual environment (optional but recommended):

```bash
python -m venv .venv
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Set up environment variables:

1. Copy the example file:
    ```bash
    cp .env.example .env
    ```
2. Edit `.env` and populate the required values.

---

## 🛠️ Development Commands (via `invoke`)

These commands streamline local development. Run them using [`invoke`](https://www.pyinvoke.org/):

```bash
invoke <command>
```

| Command         | Description                                                                 |
|-----------------|-----------------------------------------------------------------------------|
| `invoke run`    | Run the bot (`main.py`)                                                     |
| `invoke venv`   | Activate the virtual environment (assumes `.venv/bin/activate`)             |
| `invoke lint`   | Lint the codebase using Ruff                                                |
| `invoke fix`    | Automatically fix lint issues with Ruff                                     |
| `invoke format` | Format the code using Ruff’s formatter                                      |
| `invoke all`    | Run `lint`, `fix`, and `format` in sequence (for full code quality check)   |

> **Note:** Ensure `ruff` and `invoke` are installed:
> ```bash
> pip install ruff invoke
> ```

---

## 🐳 Building and Pushing Docker Image

To build and push a multi-platform Docker image:

```bash
docker buildx create --use --name multi-platform-builder --driver docker-container
docker buildx build --platform linux/amd64,linux/arm64 -t brentonmdunn/ride-bot --push .
```

---

## 📦 Deploying to Synology NAS (via Container Manager)

1. Pull the Docker image from [Docker Hub](https://hub.docker.com/r/brentonmdunn/ride-bot)
2. Enable auto-restart
3. Map volume:  
   `/volume1/docker/lscc-discord-bot` → `/app/db:rw`
4. Load environment variables from your `.env` file

---

## 🧪 GitHub Workflows

- **Pull Requests**
  - Each PR runs **lint** and **format** checks via GitHub Actions
  - PRs that fail these checks will be blocked from merging

- **Main Branch Merges**
  - After merging to `main`, a workflow builds and pushes the Docker image to Docker Hub

- **Branch Protection**
  - Direct commits to `main` are prohibited  
    All changes must go through a PR and pass required checks

