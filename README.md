# Rides Coordinator Bot

[![Python](https://img.shields.io/badge/python-3.13-blue.svg)](https://www.python.org/downloads/)
[![React](https://img.shields.io/badge/react-18-blue.svg)](https://react.dev/)
[![Docker](https://img.shields.io/badge/docker-build-blue.svg)](https://www.docker.com/)

A comprehensive Discord bot and web dashboard for coordinating ride pickups, managing events, and tracking driver availability.

## 🏗️ Architecture

This project is a monorepo consisting of:

- **Backend (`backend/`)**: A Python application using `discord.py` for the bot and `FastAPI` for the web API and admin interface. See the [Backend Architecture Guide](backend/docs/architecture.md) for more structural details.
- **Frontend (`frontend/`)**: A React SPA built with Vite and TailwindCSS for the user dashboard.

**High-Level Flow:**
- The Discord bot acts as the primary interface for users to interact with features (slash commands, buttons, reactions).
- The FastAPI application serves as the system's brain and database interface, securely communicating with the frontend React SPA.
- The React SPA serves as an admin dashboard to visualize and manipulate the data (e.g., viewing pickups, feature flags, group rides).

## 📚 Documentation & Guides

- [Documentation Hub](docs/README.md)
- [Contributing Guide](CONTRIBUTING.md)
- [CI/CD Strategy](docs/CI_CD.md)
- [Frontend Config](frontend/ENV_CONFIG.md)

## 🚀 Quick Start

### 1. Backend Setup
Navigate to the `backend` directory to set up the Python environment, install dependencies, and run the bot/API.

[👉 Go to Backend Documentation](backend/README.md)

### 2. Frontend Setup
Navigate to the `frontend` directory to install Node.js dependencies and start the development server.

[👉 Go to Frontend Documentation](frontend/README.md)

## 🐳 Docker Support

The entire application can be containerized. CI/CD pipelines are configured to build multi-platform images on merge to main.

```bash
docker pull brentonmdunn/ride-bot
```
