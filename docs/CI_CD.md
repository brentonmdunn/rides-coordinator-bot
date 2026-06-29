# CI/CD Strategy

This project uses two independent GitHub Actions workflows for Docker builds and deployments.

## How it Works

1. **Pull Request (`docker-preprod.yml`)**:
   - Triggered when a PR is opened or updated targeting the `main` branch.
   - Builds the frontend, bundles it with the backend, and creates a Docker image.
   - Pushes to `brentonmdunn/ride-bot-preprod`.
   - Tags: `latest` and the PR head SHA.

2. **Merge to Main (`docker-prod.yml`)**:
   - Triggered when code is pushed to `main` (usually via a PR merge).
   - Independently rebuilds the frontend and backend Docker image from source.
   - Pushes to `brentonmdunn/ride-bot`.

Both workflows build independently from source — there is no image promotion or retagging between preprod and prod.

## Troubleshooting

If the production deployment fails or seems out of date, manually trigger a new build by opening and merging a small PR.
