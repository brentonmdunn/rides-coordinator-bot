---
trigger: always_on
---

# Docker & Deployment

## Docker

- Main Dockerfile: `backend/Dockerfile`
- Preprod Dockerfile: `backend/Dockerfile.preprod`
- Image: `brentonmdunn/ride-bot`
- CI/CD builds multi-platform images on merge to `main` (see `.github/workflows/`).

## Environment Configs

All in `backend/`:

- `.env.dev` — Local development
- `.env.preprod` — Pre-production
- `.env.prod` — Production
- `.env.example` — Template for new setups

## Frontend Deployment

- Deploy script: `deploy-frontend.sh` (root of repo)
- Build output: `frontend/dist/`

## CI/CD

- Workflows are in `.github/workflows/`.
- Docker startup test runs on PRs to validate the image builds and starts correctly.
