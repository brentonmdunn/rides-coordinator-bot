# CI/CD Strategy: Image Promotion

This project uses an **Image Promotion** strategy (Build Once, Deploy Many) for Docker deployments.

## How it Works

1.  **Pull Request (Build & Test)**:
    - Triggered when a PR is opened or updated targeting the `main` branch.
    - Builds the frontend, bundles it with the backend, and creates a Docker image.
    - Pushes this image to `brentonmdunn/ride-bot-preprod`.
    - Tags: `latest` and `${{ github.event.pull_request.head.sha }}`.

2.  **Merge to Main (Promotion)**:
    - Triggered when code is pushed directly to `main` (usually via a PR merge).
    - Pulls the `latest` image from the **preprod** repository.
    - Re-tags it for the **production** repository (`brentonmdunn/ride-bot`).
    - Pushes to production.

## Why this is standard
- **Immutability**: You deploy the exact same binary (layer for layer) that you reviewed in the PR.
- **Efficiency**: No need to rebuild the entire image twice.
- **Reliability**: Eliminates "it worked in staging but the build failed for prod" issues.

## Important Warnings

> [!CAUTION]
> **Direct Pushes to Main**:
> If you push code directly to the `main` branch without going through a Pull Request, the promotion job will pull the **most recent image** from the preprod repository (likely from a previous PR) and push it to production. 
> 
> **Always use Pull Requests to ensure your latest changes are built and promoted correctly.**

## Troubleshooting
If the production deployment fails or seems out of date, manually trigger a new build by opening and merging a small PR.
