# Route Builder — UI/UX Proposals

> **Status:** The five quick-wins (#1, #2, #4, #6, #16) are **resolved** and shipped.
> Each resolved section below is marked `✓ Resolved` with a brief implementation
> note. Remaining items are open for follow-up.

Files reviewed:

- `frontend/src/components/RouteBuilder/RouteBuilder.tsx` (orchestrator)
- `frontend/src/components/RouteBuilder/RouteBuilderWidget.tsx` (card view)
- `frontend/src/components/RouteBuilder/RouteBuilderFullscreenMap.tsx`
- `frontend/src/components/RouteBuilder/RouteBuilderDesktopPanel.tsx`
- `frontend/src/components/RouteBuilder/RouteBuilderMobileSheet.tsx`
- `frontend/src/components/RouteBuilder/RouteBuilderPanelContents.tsx`
- `frontend/src/components/RouteBuilder/routeBuilderShared.tsx`
- `frontend/src/components/RouteBuilder/routeBuilderConstants.ts`
- `frontend/src/components/RouteBuilder/useRouteGeometry.ts`
- `frontend/src/components/EditableOutput.tsx`

Note: the pre-refactor flat `frontend/src/components/RouteBuilder.tsx` was deleted as part of the quick-wins PR — only the modular folder version remains.

Suggestions are grouped by priority. P1 = high impact / low cost, P2 = medium, P3 = nice-to-have.

---

## 1. Adding stops — flow inconsistencies (P1) — ✓ Resolved

*Implemented in `LocationCombobox.tsx` (multi-select combobox with search) and the
widget mini-map (clickable markers that toggle stops). The dropdown stays open
for rapid multi-select; selected rows show a check, unselected rows show a `+`.*


**Today:**

- Widget view: pick from a dropdown, then click "Add Location" (two clicks per stop).
- Fullscreen view: tap pins on the map (one tap per stop). Selected pins turn green with a number.
- The widget has no map-tap-to-add (the mini-map is non-interactive). The fullscreen panel has no list dropdown.

**Friction:**

- Two completely different mental models for the same action depending on which view you're in.
- In the widget, the dropdown closes after each pick and you have to click "Add Location" to commit, then re-open the dropdown for the next stop. Adding 5 stops = 10+ clicks.
- The dropdown filters out already-selected entries, which is good, but there's no search/typeahead. With many locations, it becomes a long scroll.

**Proposals:**

- Make the dropdown a **multi-select combobox with checkboxes** (the existing shadcn `Command` / `Popover` primitives in this repo would do it). Stops are added on click, "Add Location" button goes away.
- Add a **search input** at the top of the dropdown (filter by location name).
- Make the **mini-map markers also clickable** — one click to add, click again to remove. This makes the widget consistent with the fullscreen flow without having to expand.
- When no stops are selected, the mini-map could show a subtle hint overlay ("Tap a marker or pick from the list above") similar to the empty-state already used in the fullscreen panel.

## 2. Mini-map vs fullscreen visual parity (P1) — ✓ Resolved

*Implemented by extracting `createNumberedIcon` into `numberedMarker.ts` and
using it in both `RouteBuilderWidget` and `RouteBuilderFullscreenMap`. The
polyline color/weight is unchanged and already consistent.*


**Today:**

- Fullscreen map: numbered green markers (1, 2, 3…) for selected stops, plain blue pins for the rest.
- Mini-map: all selected stops use the **default blue pin**, with the order only revealed inside a popup on click.

**Friction:**

- Users can't see the route order at a glance from the widget. They have to expand to fullscreen just to verify ordering visually.

**Proposal:** Use the same `createNumberedIcon(orderIndex + 1, …)` markers in both the widget mini-map and the fullscreen map. Same goes for the polyline color/weight (already consistent — keep that).

## 3. Discoverability of fullscreen mode (P2)

**Today:** A small expand icon in the card header (top-right) is the only entry point to fullscreen.

**Proposals:**

- Add a secondary, more prominent "**Open full map**" button near the mini-map (overlay or below). The mini-map is the most likely place a user expects to interact with the map.
- Surface a tooltip / hint on first visit (one-time) that fullscreen exists.
- Allow clicking the mini-map itself to enter fullscreen.

## 4. Route output — surface useful trip metadata (P1) — ✓ Resolved

*Implemented by extending `useRouteGeometry` to return total duration, total
distance, and per-leg durations from OSRM. The widget and fullscreen panel now
show a summary chip (`24 min · 7.3 mi`) and per-leg drive labels (`↓ 5 min`)
between rows in the sortable list. Pickup-time-per-stop remains driven by the
backend's formatted route string.*


**Today:** OSRM is queried for route geometry, but only the polyline is used. The Discord-formatted text is the only output.

**Proposals:**

- Display **estimated total drive time** and **total distance** (both already returned by OSRM in the same response — `data.routes[0].duration` and `…distance`). Put a small chip row under the route order: `~24 min · 7.3 mi`.
- Show **per-leg ETAs** in the sortable list (e.g., `1. Mesa Verde — 7:42pm`). The bot already computes pickup times server-side in `make_route`, but the UI doesn't echo them outside of the final formatted string. Parse them once and render them inline in the list rows.
- Bonus: little arrow direction badges between rows (e.g., `↓ 4 min`).

## 5. Generated-route textarea — clarity & affordances (P2)

**Today:** A monospace textarea with Copy + Revert buttons that fade in on hover/focus on desktop (always visible on mobile).

**Friction & proposals:**

- The "↩ Revert" button only appears when content differs from the original. There's no visible indicator that the text *is* edited otherwise — add an "Edited" pill or a subtle dot in the corner.
- "Copy" success state lasts 5s, which is good, but the button text contains an emoji that varies in size across platforms. Consider replacing with `lucide` `Copy` / `Check` icons that already pattern-match the rest of the UI (the InfoToggleButton, ChevronRight, etc.).
- Add a **"Preview as Discord message"** toggle that renders mentions (`@name`) and bold text the way Discord would. This builds confidence before pasting.
- Add a "Copy without driver mention" option when a driver is selected (right now the prefix is forced; a one-click toggle is friendlier than manually editing).
- When the route is regenerating, the textarea currently keeps the previous output until the new one arrives. Consider greying it out / showing a subtle skeleton so users don't paste a stale route.

## 6. Driver selector placement (P2) — ✓ Resolved

*Implemented by extracting the driver `Select` into a shared `DriverSelector`
component rendered in both the widget card and the fullscreen panel/sheet. The
selector is now visible as soon as drivers are loaded for the day, regardless
of whether a route has been generated yet, and works in both views
identically.*


**Today:** Only present in the fullscreen panel (`RouteBuilderPanelContents`), and only after a route is generated.

**Friction:** Users in the widget view can't pick a driver at all — they get an unprefixed route and have to either edit the textarea by hand or expand to fullscreen. This is asymmetric.

**Proposals:**

- Move the driver selector into a shared sub-component used by both the widget and the panel.
- Allow selecting a driver **before** the route exists (the prefix is purely cosmetic; nothing depends on a route being generated).
- If the driver list comes back empty (`uniqueDrivers.length === 0`), show a small empathy line: "No drivers have responded for {Friday|Sunday} yet."

## 7. Auto-detected time — make the "auto" state visible (P2)

**Today:** `getAutomaticDay()` silently picks the preset on mount. The user sees a highlighted preset but no explanation why.

**Proposal:** Add a small "Auto-detected" pill next to the highlighted preset on first render. Clearing/changing the selection removes the pill. Helps avoid the "wait, why did it pick Sunday?" confusion on, say, a Saturday.

## 8. Time presets vs custom input (P2)

**Today:** Custom time uses a free-form text field with parser-friendly formats (`7:10pm`, `7p`, `19:10`).

**Proposals:**

- Use `<input type="time">` for the custom field. Browsers handle 12/24h conversion natively, prevent typos, and on mobile bring up a wheel picker. You can still parse the resulting `HH:MM` server-side.
- Or, keep the freeform field but add a small live-validation hint (red border + "Couldn't parse this time") instead of the silent fail mode.
- Group the preset rows by day (Friday vs. Sunday) so it's visually obvious which presets belong together. Right now the four event presets are all in one row.

## 9. Sortable list — drag & drop polish (P2)

**Today:** `dnd-kit` with a `GripVertical` handle. Pointer activation `distance: 8`.

**Friction & proposals:**

- The grip handle is small and easy to miss on mobile. Either expand the handle's hit area (e.g., `p-2`) or make the **whole row** the drag activator with a long-press constraint on touch (`useSensor(TouchSensor, { activationConstraint: { delay: 200, tolerance: 5 } })`).
- Add keyboard hints: `aria-describedby` on each item with text like "Press space to pick up, arrow keys to move." `dnd-kit` already supports keyboard reordering — just expose it.
- The "X" remove icon is also `lucide-react`, same shape used elsewhere for "close panel/overlay." Consider `Trash2` or a small explicit "Remove" tooltip on hover so users don't second-guess.
- Add a subtle drop animation (e.g., `framer-motion` or `dnd-kit`'s `restrictToVerticalAxis` modifier with a `dropAnimation`) for a more tactile feel.

## 10. "Tap pins to build your route" empty state (P2)

**Today:** Shown only when `selectedLocationKeys.length === 0`.

**Proposals:**

- After the first stop is added, show a smaller **persistent hint** ("Tap more pins to add stops · drag to reorder") until the user has 2+ stops, then dismiss it.
- The empty state currently says "Tap on map markers." On desktop, "tap" should be "click" (or use both: "Click pins to add stops").

## 11. Fullscreen back button placement (P2)

**Today:** Floating button at `top-24 left-4`. That's well below the screen edge — it visually feels orphaned, especially on tall screens.

**Proposals:**

- Move it to `top-4 left-4` (corner) and stack the Leaflet zoom controls below it, OR
- Put it inside a translucent header bar across the top (matches modern map apps like Google Maps fullscreen / Apple Maps).
- The `ESC` hint pill is a nice touch but only shows on desktop (`!isMobile`); fine, but consider showing the same kbd hint as a tooltip on hover.

## 12. Desktop side-panel collapsed state (P3)

**Today:** When collapsed, the panel disappears entirely except for a tiny chevron handle in emerald.

**Proposal:** Show a small **count badge** next to the handle when collapsed (e.g., a green circle with `3` if 3 stops). Otherwise the user has no indication the panel still has state.

## 13. Mobile bottom sheet — gesture support (P3)

**Today:** The component doc-comment explicitly states "No swipe gesture — uses explicit tap targets." Tapping anywhere on the header expands/collapses; checkbox + clear button stop propagation.

**Proposals:**

- Add a swipe-to-expand / swipe-to-collapse gesture (Vaul or `@radix-ui/react-dialog`'s drawer primitives). It's the dominant interaction model for bottom sheets and feels missing here.
- The header bar is dense on small screens (icon + label + checkbox + Clear pill + chevron). Consider moving "Show labels" into the expanded body so the header stays scannable.
- The chevron pill background uses emerald even when collapsed; consider neutral when collapsed and emerald when there's an active selection (matches the desktop pattern where the collapsed handle is emerald only when collapsed/has-state).

## 14. Map controls — missing "Fit to selection" (P2)

**Today:** The mini-map has a `RecenterMap` that auto-fits when `mapBounds` changes. The fullscreen map does **not** auto-fit; it stays at zoom 14 over UCSD.

**Proposals:**

- Add a **"Fit to route"** button (e.g., bottom-right of the fullscreen map) that calls `map.fitBounds(...)` over the selected stops. Useful after panning/zooming around.
- Add a "Zoom to my location" button (`navigator.geolocation`) for drivers who want to orient themselves quickly.
- Map clicks currently call `MapClickHandler` with `() => {}` — i.e., empty handler. Either remove it (dead code) or use it (e.g., dismiss popups on background click).

## 15. Optional route optimization (P3)

**Today:** Stops are visited in the order entered/dragged. OSRM offers a `/trip` endpoint that solves a TSP-style optimal ordering.

**Proposal:** Add an "**Optimize order**" button. It calls OSRM's trip service and reorders the stops by shortest total drive time, with a 1-click "Undo" / "Restore my order". Reduces driver distance and time.

## 16. Persistence (P2) — ✓ Resolved

*Implemented in `RouteBuilder.tsx`: selected stops, time mode, leave time, and
selected driver are mirrored to `localStorage` (key `routeBuilder.state.v1`)
and to URL search params (`rb_stops`, `rb_time_mode`, `rb_leave_time`,
`rb_driver`). URL params take precedence over localStorage on initial load so
shared links restore the route. Stops referencing locations no longer in the
backend list are silently dropped on first hydration.*


**Today:** Selected stops, time mode, custom time, and selected driver live entirely in component state. A page refresh or accidental navigation wipes them.

**Proposals:**

- Persist `selectedLocationKeys`, `timeMode`, `leaveTime`, and `selectedDriver` to `localStorage` (or sync to `user-preferences` since that table already exists). Restore on mount.
- Encode the route in the URL (`?stops=a,b,c&time=7:10pm`) so users can share a draft. Bonus: makes screenshots/help threads easier ("Why is my route weird?" → paste link).

## 17. Error & loading states (P2)

**Today:**

- Route generation: error string is rendered via `ErrorMessage`, but `Unknown error` for network failures.
- OSRM polyline: silent failure, only `console.error`. The map just doesn't draw the polyline.
- Locations fetch: `locationsLoading` only disables the dropdown; no skeleton anywhere.

**Proposals:**

- For OSRM failures, show a tiny inline note near the map: "Couldn't draw the route line. Stops are still correct." with a "Retry" link.
- For `make-route` failures, show a **Retry** button next to the error message instead of forcing the user to re-trigger by editing inputs.
- Add a skeleton state for the location dropdown (placeholder rows) and the mini-map (gradient block) while data is loading.

## 18. Accessibility cleanups (P2)

- Time-preset compact pill buttons lack `aria-pressed={timeMode === opt.key}`. Screen readers can't distinguish active vs inactive.
- Numbered marker `DivIcon` HTML has no `aria-label` / `role="img"`. Screen readers ignore them entirely. Add `aria-label="Stop {n}: {name}"`.
- "Show labels" checkbox label has a 44px hit area on mobile (good) but the visible label "Labels" is 12px; consider increasing.
- The drag-handle `<div>` should be a `<button>` (or have `role="button"` + `tabIndex=0`) so keyboard users can focus it. `dnd-kit` supports this via `attributes` — just spread them onto a focusable element.
- Many color decisions are emerald; verify contrast ratio on the dark theme variant (especially `text-emerald-400 on bg-zinc-900/95` for the chevron pill).
- The fullscreen overlay is rendered into `document.body` via portal but doesn't trap focus or set `aria-modal="true"`. A user tabbing inside fullscreen mode can land on background page elements.

## 19. Information density / hierarchy in the widget (P3)

The widget card stacks: title row → info panel → dropdown+button → list → time presets → custom input → loading → error → output → mini-map. On a phone this is a long card that requires several scrolls.

**Proposals:**

- Collapse the **Info** panel content by default (already collapsible — good) and shorten the steps from 4 to 3 by combining "select" + "drag to reorder" into one bullet.
- Move the mini-map **above** the route output. The map is the visual anchor; it should appear before the textarea so users can confirm the route shape before reaching for the copy button.
- Sticky the "Generated Route" header + Copy button on the widget so users on mobile don't have to scroll back up after editing.

## 20. Visual polish nitpicks (P3)

- The 🗺️ emoji in the card title is the only emoji-as-icon in this view, while everything else uses lucide. Replace with `Map` or `Route` icons for visual consistency.
- The mini-map height (`h-52 sm:h-[350px]`) feels short on tablets. Consider a `md:h-[400px] lg:h-[480px]` step.
- The route polyline is `#10b981` with weight 4 / opacity 0.8. On the dark CARTO tile layer this is fine; on the light tile layer it can blend with grass/parks. Consider a 1px white outer stroke (rendered as two stacked Polylines) for contrast.
- The numbered marker animation (`animate-[marker-bounce_0.35s_ease-out]`) is nice on add but absent on reorder. Triggering the same bounce when the index changes would be a delightful detail.
- Tooltips are `permanent direction="top"`. At low zoom or with many markers they overlap and become unreadable. Consider auto-hiding labels below a certain zoom level (`useMapEvents('zoomend', ...)`).

---

## Quick-win shortlist (if you only do five) — ✓ All shipped

1. ✓ **Multi-select combobox + map-click-to-add in the widget** (#1) — biggest reduction in clicks per route.
2. ✓ **Numbered markers in the mini-map** (#2) — instant ordering visibility, ~10 lines.
3. ✓ **ETA + distance chip + per-leg times** (#4) — the data is already in the OSRM response.
4. ✓ **Driver selector available in widget mode** (#6) — fixes a real asymmetry.
5. ✓ **localStorage persistence + URL state** (#16) — frequent papercut for users who refresh mid-planning.
