import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { MemoryRouter, Routes, Route, useLocation, useSearchParams } from "react-router-dom"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import type { AskRidesReactionsData } from "../types"

// ── Mock the network boundary, not auth ──────────────────────────────────
const { apiFetch } = vi.hoisted(() => ({ apiFetch: vi.fn() }))
vi.mock("../lib/api", () => ({
  apiFetch,
  ApiError: class ApiError extends Error {
    status: number
    constructor(status: number, message: string) {
      super(message)
      this.status = status
    }
  },
  getApiUrl: (endpoint: string) => endpoint,
}))

import ReactionDetails from "./ReactionDetails"

function reactionsResponse(overrides: Partial<AskRidesReactionsData> = {}): AskRidesReactionsData {
  return {
    message_type: "friday",
    reactions: {},
    username_to_name: {},
    message_found: true,
    ...overrides,
  }
}

beforeEach(() => {
  apiFetch.mockImplementation(async (endpoint: string) => {
    const match = endpoint.match(/^\/api\/ask-rides\/reactions\/(.+)$/)
    const messageType = match ? match[1] : "friday"
    return {
      ok: true,
      json: async () => reactionsResponse({ message_type: messageType as AskRidesReactionsData["message_type"] }),
    } as Response
  })
})

afterEach(() => vi.clearAllMocks())

// Reads react-router's own view of the URL via useSearchParams, so
// assertions don't depend on jsdom's window.location and stay in sync with
// whatever ReactionDetails calls setSearchParams with.
function SearchParamsReporter({
  onChange,
  onHashChange = () => {},
}: {
  onChange: (search: string) => void
  onHashChange?: (hash: string) => void
}) {
  const [searchParams] = useSearchParams()
  const location = useLocation()
  onChange(searchParams.toString())
  onHashChange(location.hash)
  return null
}

function renderAt(
  initialPath: string,
  onLocationChange: (search: string) => void = () => {},
  onHashChange: (hash: string) => void = () => {},
) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[initialPath]}>
        <Routes>
          <Route
            path="/"
            element={
              <>
                <ReactionDetails />
                <SearchParamsReporter onChange={onLocationChange} onHashChange={onHashChange} />
              </>
            }
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe("ReactionDetails deep link (?overview=...)", () => {
  it("selects Sunday from the overview param and strips only that param", async () => {
    let lastSearch = ""
    let lastHash = ""
    renderAt(
      "/?overview=sunday&foo=bar#reactions",
      (s) => {
        lastSearch = s
      },
      (h) => {
        lastHash = h
      },
    )

    await screen.findByRole("button", { name: /Sunday Service/ })
    await waitFor(() => expect(apiFetch).toHaveBeenCalledWith("/api/ask-rides/reactions/sunday"))

    await waitFor(() => {
      expect(lastSearch).not.toContain("overview")
      expect(lastSearch).toContain("foo=bar")
      expect(lastHash).toBe("#reactions")
    })
  })

  it("falls back to the automatic day when there is no overview param", async () => {
    let lastSearch = "unset"
    renderAt("/", (s) => {
      lastSearch = s
    })

    await waitFor(() => expect(apiFetch).toHaveBeenCalled())
    const [endpoint] = apiFetch.mock.calls[0]
    expect(endpoint).toMatch(/^\/api\/ask-rides\/reactions\/(friday|sunday|sunday_class)$/)
    // No overview param existed, so nothing needed stripping.
    expect(lastSearch).toBe("")
  })

  it("ignores an invalid overview value and falls back to the automatic day", async () => {
    renderAt("/?overview=not-a-real-day")

    await waitFor(() => expect(apiFetch).toHaveBeenCalled())
    const [endpoint] = apiFetch.mock.calls[0]
    expect(endpoint).toMatch(/^\/api\/ask-rides\/reactions\/(friday|sunday|sunday_class)$/)
    expect(endpoint).not.toBe("/api/ask-rides/reactions/not-a-real-day")
  })

  it("does not change the URL when a user clicks a different tab", async () => {
    let lastSearch = "unset"
    const user = userEvent.setup()
    renderAt("/?overview=sunday", (s) => {
      lastSearch = s
    })

    await screen.findByRole("button", { name: /Sunday Service/ })
    await waitFor(() => expect(lastSearch).toBe(""))

    await user.click(screen.getByRole("button", { name: /Friday Fellowship/ }))

    await waitFor(() => expect(apiFetch).toHaveBeenCalledWith("/api/ask-rides/reactions/friday"))
    expect(lastSearch).toBe("")
  })
})
