# Contributing to Rides Coordinator Bot

Thank you for your interest in contributing to the Rides Coordinator Bot! This document outlines our standard development workflow.

## General Workflow

1. **Fork & Clone:** Fork the repository and clone it locally.
2. **Branching:** Create a descriptive branch name from `main` (e.g., `feature/add-new-ride-type` or `fix/button-alignment`).
3. **Draft PR:** Open a Pull Request as early as possible with the "Draft" status to let others know what you are working on.
4. **Code Quality:** Ensure your code passes all linting and testing requirements before requesting a review.
5. **Review & Merge:** Once reviewed and approved, code is merged back into `main`. The CI/CD pipeline will automatically build and promote the Docker image.

## Backend Development (Python)

We use `uv` for dependency management and `ruff` for linting/formatting. All backend code MUST abide by the strict `Cog -> Service -> Repository` pattern for separation of concerns.

Before committing backend changes:
```bash
cd backend
uv run invoke all # Runs ruff lint, fix, and format
uv run invoke test # Runs pytest
```

Please note: All undocumented functions must include a Google-style docstring.

## Frontend Development (React/Vite)

The frontend uses React and TypeScript with TailwindCSS. Keep UI components functionally focused and extract data-fetching logic into custom hooks.

Before committing frontend changes:
```bash
cd frontend
npm run lint
```

Ensure newly added typescript types and shared components have JSDoc comments describing their behaviors.

## CI/CD and Deployments
Please refer to the [CI/CD Strategy](docs/CI_CD.md) document to understand how Docker images are generated and promoted to production upon merging to `main`.
