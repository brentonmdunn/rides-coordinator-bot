# Rides Coordinator Bot

[![Python](https://img.shields.io/badge/python-3.13-blue.svg)](https://www.python.org/downloads/)
[![React](https://img.shields.io/badge/react-18-blue.svg)](https://react.dev/)
[![Docker](https://img.shields.io/badge/docker-build-blue.svg)](https://www.docker.com/)

A comprehensive Discord bot and web dashboard for coordinating ride pickups, managing events, and tracking driver availability.

## 🏗️ Architecture

This project is a monorepo consisting of:

- **Backened (`backend/`)**: A Python application using `discord.py` for the bot and `FastAPI` for the web API and admin interface.
- **Frontend (`frontend/`)**: A React SPA built with Vite and TailwindCSS for the user dashboard.

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
