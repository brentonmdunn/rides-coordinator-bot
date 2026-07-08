# Proposal: @mention Autocomplete in EditableOutput

## Goal

When a user types `@` in any `EditableOutput` textarea, show a dropdown of Discord usernames from the `locations` table. Users can navigate with arrow keys and press Enter (or click) to insert the username. The dropdown dismisses on Escape or when the cursor leaves the `@...` token.

---

## Backend: New API Endpoint

Add `GET /api/usernames` to `backend/api/routes/` (new file `usernames.py`).

**Response:**
```json
{ "usernames": ["alice", "bob", "charlie"] }
```

- Queries `LocationsModel.discord_username` for all non-null rows — one `SELECT` over ≤100 rows.
- Public endpoint, no auth required.
- Add a new method to `LocationsRepository`: `get_all_discord_usernames(session) -> list[str]`.
- Wire up via a `LocationsService` method that opens a session and delegates to the repo.

---

## Frontend: Data Fetching

Add a `useUsernames` hook (e.g. `src/hooks/useUsernames.ts`) using `@tanstack/react-query`:

```ts
export function useUsernames() {
  return useQuery({
    queryKey: ['usernames'],
    queryFn: () => apiFetch('/api/usernames').then(r => r.usernames as string[]),
    staleTime: 5 * 60 * 1000, // 5 min — the list rarely changes
  })
}
```

This keeps the list cached across all `EditableOutput` instances on the page with no redundant fetches.

---

## Frontend: Mention State Hook

Extract mention-tracking logic into `src/hooks/useMentionAutocomplete.ts`:

```ts
export function useMentionAutocomplete(
  value: string,
  cursorPos: number,
  usernames: string[]
) {
  // Returns: { query, suggestions, activeIndex, setActiveIndex }
  // - query: the text after the @ up to the cursor, or null if not in a mention
  // - suggestions: usernames filtered by query (case-insensitive prefix match)
  // - activeIndex / setActiveIndex: keyboard navigation state
}
```

**Detection logic:** walk backwards from `cursorPos`; if we find `@` before a space/newline, we're in a mention token. The query is the substring between `@` and the cursor.

**Matching:** case-insensitive substring match (e.g. `ice` matches `alice`). Capped at 5 results. If no usernames match, show a "No results" item (non-selectable).

---

## Frontend: EditableOutput Changes

`EditableOutput` becomes a controlled textarea with a positioned dropdown overlay.

### New props (all optional, with defaults that preserve current behavior):
```ts
interface EditableOutputProps {
  // ... existing props unchanged ...
  usernames?: string[]   // pass from useUsernames(); omit to disable autocomplete
}
```

### Rendering changes:

Wrap the existing `<div>` in a `position: relative` container. Render the dropdown as an absolutely-positioned `<ul>` when `suggestions.length > 0`.

```
┌─────────────────────────────────┐
│ textarea (existing)             │
│                                 │
│ @ali|                           │
│       ┌──────────────────┐      │
│       │ alice          ← │      │ ← dropdown, positioned below cursor
│       │ alicia           │      │
│       └──────────────────┘      │
└─────────────────────────────────┘
```

**Positioning:** pinned to the bottom-left corner of the textarea container for now. May be changed later to follow the cursor if the UX feels off.

### Keyboard handling (added to the `<textarea>` `onKeyDown`):

| Key | Behavior |
|-----|----------|
| `↑` / `↓` | Move `activeIndex` (with wraparound). Prevent default scroll. |
| `Enter` | Insert the selected username; close dropdown. Prevent default newline only when dropdown is open. |
| `Escape` | Close dropdown without inserting. |
| Any other key | Passed through normally; autocomplete re-evaluates on each keystroke. |

**Blur:** if the user clicks outside the textarea (and not on a dropdown item), the dropdown closes immediately.

### Insertion logic:

Replace the `@query` token (from the `@` up to `cursorPos`) with `@username ` (trailing space), then set cursor to end of insertion.

---

## Component Tree Summary

```
EditableOutput
  props: { ..., usernames? }
  hooks: useMentionAutocomplete(value, cursorPos, usernames)
  renders:
    <div (relative)>
      <textarea onChange/onKeyDown/onSelect />
      {suggestions.length > 0 && <MentionDropdown />}
    </div>

MentionDropdown (new, internal or same file)
  props: { suggestions, activeIndex, onSelect }
  renders: <ul> with <li> per suggestion, highlighting activeIndex

--- call site (e.g. RouteBuilderPanelContents) ---
const { data: usernames } = useUsernames()
<EditableOutput ... usernames={usernames} />
```

---

## Files to Create / Modify

| File | Change |
|------|--------|
| `backend/bot/repositories/locations_repository.py` | Add `get_all_discord_usernames` static method |
| `backend/bot/services/locations_service.py` | Add `get_all_discord_usernames` method |
| `backend/api/routes/usernames.py` | New file — `GET /api/usernames` |
| `backend/api/main.py` (or router file) | Register new router |
| `frontend/src/hooks/useUsernames.ts` | New file — React Query hook |
| `frontend/src/hooks/useMentionAutocomplete.ts` | New file — mention detection + suggestion logic |
| `frontend/src/components/EditableOutput.tsx` | Add `usernames` prop + dropdown rendering + keyboard handling |
| `frontend/src/components/RouteBuilder/RouteBuilderPanelContents.tsx` | Thread `useUsernames` data into `EditableOutput` |

All call sites that render `EditableOutput` will pass `usernames` — this includes RouteBuilder and GroupRides.

---

## What This Does NOT Do

- No server-side filtering — the full list is fetched once and filtered in memory.
- No rich @mention rendering (coloring, chips) — the textarea stays plain text.
- Dropdown does not follow the cursor — pinned to bottom-left of the textarea.
