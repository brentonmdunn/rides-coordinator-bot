---
trigger: always_on
---

# Frontend Conventions

The frontend is a React 19 SPA in `frontend/`, built with Vite and Tailwind CSS v4.

## Architecture

- **Components** (`src/components/`): Reusable UI components. Uses shadcn/ui (`components.json` present).
- **Pages** (`src/pages/`): Top-level page components.
- **Types** (`src/types.ts`): Shared TypeScript type definitions.
- **Utilities** (`src/lib/utils.ts`): Shared helper functions (e.g., `getAutomaticDay`, `useCopyToClipboard`).

## Key Libraries

- **@tanstack/react-query**: Server state management and data fetching.
- **react-router-dom**: Client-side routing.
- **@dnd-kit**: Drag-and-drop functionality.
- **lucide-react**: Icon library.
- **class-variance-authority** + **clsx** + **tailwind-merge**: Conditional styling utilities (shadcn pattern).

## Standards

- Use TypeScript — no `any` types.
- Run `npm run lint` (ESLint) before committing frontend changes.
- Environment configs: `.env.development` (local) and `.env.production`.
- Build with `npm run build` (`tsc -b && vite build`).
