# Documentation Hub

Welcome to the central documentation hub for the Rides Coordinator Bot project.

## Project Structure & Architecture

The project consists of three main components working together:

1. **Discord Bot (Python):** Handles incoming slash commands, reactions, and direct engagement with users.
2. **Backend API (FastAPI):** Controls business logic, talks to the SQLite database, and serves data. [Read the Backend Architecture Guide](../backend/docs/architecture.md)
3. **Frontend Dashboard (React):** Administrative SPA allowing managers to visualize pickup coverages and coordinate rides. [View Frontend Environment Details](../frontend/ENV_CONFIG.md)

## Development & Contribution

If you want to contribute, please start by reading the [Contributing Guide](../CONTRIBUTING.md) which details branching, PRs, and linting requirements.

## Deployment & Hosting

- **CI/CD Image Promotion:** Understand how our Pull Requests generate test Docker images and how merges automatically promote those images to production. [Read CI/CD Strategy](CI_CD.md).
