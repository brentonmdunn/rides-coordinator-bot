# Rides Coordinator Bot — Portfolio Demo

A live demo of the admin dashboard for the Rides Coordinator Bot. All data is fictional and no actions are executed against any real backend.

**Live demo:** https://brentonmdunn.github.io/rides-coordinator-bot

## What this is

The Rides Coordinator Bot is a Discord bot + web admin dashboard that manages ride logistics for recurring weekly events. It handles:

- Tracking who needs a ride and where they're being picked up
- Organizing drivers into pickup groups
- Scheduling automated ride-request messages
- Monitoring reaction-based RSVPs in real time

This `portfolio/` folder contains a standalone version of the frontend with all API calls replaced by in-memory mock data, so it can be shared publicly without exposing any real user information.

## Running locally

```bash
cd portfolio
npm install
npm run dev
```

Then open `http://localhost:5173/rides-coordinator-bot/`.

## How the demo works

- **Mock API** (`src/lib/api.ts`) — all `apiFetch` calls return hardcoded fake data. Mutations (toggling feature flags, inviting users, etc.) update an in-memory store that persists for the session and reset on page refresh.
- **Demo banner** — a persistent banner at the top of every page indicates demo mode. Any button that would trigger a real action shows a toast notification explaining this.
- **No authentication** — the app loads directly as a demo admin user with no login required.

## Tech stack

- React 19 + TypeScript
- Vite
- Tailwind CSS v4
- TanStack Query
- Leaflet (interactive map in the route builder)
- Deployed to GitHub Pages via GitHub Actions
