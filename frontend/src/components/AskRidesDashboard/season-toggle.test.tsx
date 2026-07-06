import { useState } from "react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import type { AskRidesJobStatus, AskRidesStatus, FellowshipSeason } from "@/types"

// ── Mock the network boundary, not auth ──────────────────────────────────
// Auth is a non-issue at the component layer: `apiFetch` just forwards the
// session cookie, and the route-level <AuthGuard> is what actually checks
// `/api/me`. By mocking `lib/api` we replace the whole network, so there is
// no auth to satisfy. Both components import from this same module.
const { apiFetch } = vi.hoisted(() => ({ apiFetch: vi.fn() }))
vi.mock("@/lib/api", () => ({ apiFetch }))

import AskRidesDashboard from "./AskRidesDashboard"
import SiteSettingsDialog from "@/components/SiteSettingsDialog"

// A tiny in-memory "server" that holds the season the way the backend would.
let serverSeason: FellowshipSeason

function job(): AskRidesJobStatus {
  return {
    enabled: true,
    will_send: true,
    reason: null,
    next_run: "2026-07-03T18:00:00Z",
    pause: { is_paused: false, resume_after_date: null, resume_send_date: null },
  }
}

const status: AskRidesStatus = {
  friday: job(),
  wednesday: job(),
  sunday: job(),
  sunday_class: job(),
}

function jsonResponse(body: unknown): Response {
  return { ok: true, json: async () => body } as Response
}

beforeEach(() => {
  serverSeason = "friday"
  apiFetch.mockImplementation(async (endpoint: string, options?: RequestInit) => {
    if (endpoint === "/api/ask-rides/fellowship-season") {
      if (options?.method === "POST") {
        serverSeason = JSON.parse(options.body as string).season
      }
      return jsonResponse({ season: serverSeason })
    }
    if (endpoint === "/api/ask-rides/status") return jsonResponse(status)
    throw new Error(`Unhandled endpoint in test: ${endpoint}`)
  })
})

afterEach(() => vi.clearAllMocks())

// Mirror the real app: the dashboard is always on the page, and the settings
// dialog is a modal the user opens and closes. (A radix modal marks the rest
// of the page aria-hidden while open, so the realistic open→change→close flow
// is also what keeps role-based queries on the dashboard working.)
function Harness() {
  const [open, setOpen] = useState(false)
  return (
    <>
      <button onClick={() => setOpen(true)}>Open settings</button>
      <SiteSettingsDialog open={open} onOpenChange={setOpen} canManage />
      <AskRidesDashboard canManage={false} />
    </>
  )
}

function renderApp() {
  // One QueryClient shared across the tree, exactly like the real app — this
  // is what lets the settings mutation's cache invalidation reach the
  // dashboard. Retries off so failures surface immediately.
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <Harness />
    </QueryClientProvider>,
  )
}

describe("selecting Wed. Fellowship in settings updates the dashboard", () => {
  it("flips the fellowship card from Friday to Wednesday", async () => {
    const user = userEvent.setup()
    renderApp()

    // Starts on Friday — dashboard shows the Friday Fellowship card.
    expect(await screen.findByRole("heading", { name: "Friday Fellowship" })).toBeInTheDocument()
    expect(screen.queryByRole("heading", { name: "Wed. Fellowship" })).not.toBeInTheDocument()

    // Open settings and pick Wednesday.
    await user.click(screen.getByRole("button", { name: "Open settings" }))
    await user.click(await screen.findByRole("button", { name: /Wed\. Fellowship/ }))

    // Close the modal (Escape), then the dashboard reflects the new season.
    await user.keyboard("{Escape}")
    expect(await screen.findByRole("heading", { name: "Wed. Fellowship" })).toBeInTheDocument()
    await waitFor(() =>
      expect(screen.queryByRole("heading", { name: "Friday Fellowship" })).not.toBeInTheDocument(),
    )

    // And the change was persisted via a POST, not just local state.
    expect(apiFetch).toHaveBeenCalledWith(
      "/api/ask-rides/fellowship-season",
      expect.objectContaining({ method: "POST", body: JSON.stringify({ season: "wednesday" }) }),
    )
  })
})
