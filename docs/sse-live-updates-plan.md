# Plan: Live Updates via SSE for Reaction-Derived Views

## Background

The app already has working SSE infrastructure:

- **Backend**: `bot/core/reaction_broadcaster.py` — in-process pub/sub. The `reactions` cog publishes every ride-message reaction add/remove. `api/routes/reaction_log_stream.py` exposes it as `GET /api/reaction-log/stream` (SSE, heartbeat every `SSE_HEARTBEAT_INTERVAL`, gated by `require_ride_coordinator`).
- **Frontend**: `pages/ReactionLog.tsx` and `AskRidesDashboard/MessageTemplatesEditor.tsx` each open an `EventSource` with an `onerror` → `streamError` fallback, and invalidate react-query keys on message.

Meanwhile, three other views render data **derived from those same reactions** but only fetch on mount or manual refresh:

| View | File | Current freshness |
|---|---|---|
| Ride coverage panel | `components/RideCoverageCheck.tsx` | `staleTime: 5 min`, `refetchOnWindowFocus: false`, manual sync button |
| Coverage warning banner | `components/RideCoverageWarning.tsx` | `staleTime: 5 min`, `refetchOnWindowFocus: false` |
| Rider reactions section | `components/ReactionDetails.tsx` | manual `useState` fetch + refresh button |
| Driver reactions section | `components/DriverReactions.tsx` | manual `useState` fetch + refresh button |

A coordinator watching signups during an ask-rides window sees stale data during exactly the period reactions are arriving.

## Goal

When a reaction is added/removed on a ride message, every reaction-derived view on the page updates within ~1s — with **one** SSE connection per tab, not one per component.

## Non-Goals

- No new backend event types or endpoints (reuse `/api/reaction-log/stream`).
- No live updates for admin-edited data (feature flags, users, locations) — those change only via this UI and are already invalidated by their mutations.
- No WebSockets; SSE is sufficient (server→client only) and already proven here.

## Design

### 1. Shared hook: `useReactionStream` (new — `frontend/src/hooks/useReactionStream.ts`)

A module-level singleton `EventSource` shared across all subscribers:

```ts
export function useReactionStream(onEvent: () => void): { streamError: boolean }
```

- First subscriber opens `new EventSource(getApiUrl('/api/reaction-log/stream'), { withCredentials: true })`; last unsubscriber closes it (refcount).
- `onmessage` → notify all subscribers, **debounced ~500 ms** so reaction bursts (e.g., a user toggling emojis) collapse into one refetch.
- `onerror` → set `streamError` for all subscribers, close the stream (per CLAUDE.md SSE rule). Views fall back to today's manual-refresh behavior; show the existing "live updates unavailable" hint pattern from `ReactionLog.tsx`.
- Follow the `FakeEventSource` stub pattern from `MessageTemplatesEditor.test.tsx` for tests.

### 2. Migrate `ReactionDetails` and `DriverReactions` to react-query

Both currently hand-roll `useState`/`apiFetch`. Convert to `useQuery`:

- `ReactionDetails`: `queryKey: ['askRidesReactions', selectedType]` → `/api/ask-rides/reactions/{messageType}`
- `DriverReactions`: `queryKey: ['driverReactions', activeDay]` → `/api/check-pickups/driver-reactions/{day}`

Keep the existing refresh buttons (they become `refetch()` + reset-to-auto-day). This migration is worthwhile on its own (dedupe, caching, error states) and is a prerequisite for invalidation-driven updates.

### 3. Wire invalidations

One call site per view (or one in `Home.tsx` covering its sections):

```ts
const queryClient = useQueryClient()
const { streamError } = useReactionStream(() => {
    void queryClient.invalidateQueries({ queryKey: ['rideCoverage'] })
    void queryClient.invalidateQueries({ queryKey: ['askRidesReactions'] })
    void queryClient.invalidateQueries({ queryKey: ['driverReactions'] })
})
```

- `RideCoverageCheck` / `RideCoverageWarning`: no query changes needed — existing `['rideCoverage', …]` keys are invalidated by prefix. Keep `staleTime: 5 min` as the fallback when the stream is down.
- Refactor `ReactionLog.tsx` to consume the shared hook instead of its own `EventSource` (behavior unchanged).
- `MessageTemplatesEditor` stays as-is — it consumes a different stream (`/api/ask-rides/messages/stream`).

### 4. Backend — verify, likely no changes

- Confirm the `reactions` cog publishes both **add and remove** events for all ride-message types that feed coverage (Friday, Sunday, drivers).
- Auth: `/api/reaction-log/stream` requires ride-coordinator. The coverage panel and reaction sections are coordinator-gated too, so no new endpoint needed. If viewer-role users can see `RideCoverageWarning`, the hook must degrade silently on 401/403 (treat as `streamError` without a scary banner).
- Check proxy config already handles the existing stream (it does — `X-Accel-Buffering: no` is set), so nothing new.

## Steps

1. `feat/sse-live-reactions` branch.
2. Add `useReactionStream` hook + Vitest tests (refcount open/close, debounce, error fallback).
3. Convert `ReactionDetails` and `DriverReactions` to `useQuery`.
4. Wire invalidations in `Home.tsx`; refactor `ReactionLog.tsx` to the shared hook.
5. Manual verification (local, `APP_ENV=local`): open Home + Reaction Log in two tabs, add/remove reactions on a ride message in Discord, confirm coverage panel, reaction sections, and log all update without refresh; kill the API mid-stream and confirm the fallback hint appears and manual refresh still works.
6. `npm run lint`, `npx tsc --noEmit`, `npm test`.

## Risks

- **Connection limits**: browsers cap ~6 concurrent HTTP/1.1 connections per host; the singleton hook keeps us at one stream per tab regardless of how many views subscribe.
- **Refetch storms**: debounce in the hook, and invalidation (not forced refetch) means only mounted views refetch.
- **Stream silently dead** (proxy timeout without error event): heartbeats every 30 s keep intermediaries alive; the 5-min `staleTime` + window-focus refetch on migrated queries acts as a backstop.
