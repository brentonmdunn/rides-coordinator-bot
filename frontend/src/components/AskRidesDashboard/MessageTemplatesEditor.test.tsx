import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { render, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import type {
  AskRidesCoordinator,
  AskRidesMessageTemplate,
  AskRidesMessageType,
  AskRidesMessagesResponse,
  AskRidesScheduleEntry,
  AskRidesScheduleResponse,
  AskRidesScheduleSlot,
} from "@/types"

// ── Mock the network boundary, not auth ──────────────────────────────────
// Same approach as season-toggle.test.tsx: replace `apiFetch` entirely so
// there's no real network or auth flow to satisfy in this component test.
const { apiFetch } = vi.hoisted(() => ({ apiFetch: vi.fn() }))
vi.mock("@/lib/api", () => ({
  apiFetch,
  getApiUrl: (endpoint: string) => endpoint,
}))

// jsdom doesn't implement EventSource — stub it so the component's SSE
// effect can mount/unmount without throwing. Tests don't exercise live
// push updates here; they only assert on query/mutation round trips.
class FakeEventSource {
  onmessage: (() => void) | null = null
  onerror: (() => void) | null = null
  close = vi.fn()
}
vi.stubGlobal("EventSource", FakeEventSource)

import MessageTemplatesEditor from "./MessageTemplatesEditor"

// ── Tiny in-memory "server" ──────────────────────────────────────────────

function defaultTemplate(overrides: Partial<AskRidesMessageTemplate> = {}): AskRidesMessageTemplate {
  const base: AskRidesMessageTemplate = {
    title: "Wednesday Fellowship Rides",
    body: "Need a ride to fellowship on {date}? React below!",
    color: "teal",
    reactions: ["🪨"],
    is_customized: false,
    default: {
      title: "Wednesday Fellowship Rides",
      body: "Need a ride to fellowship on {date}? React below!",
      color: "teal",
      reactions: ["🪨"],
    },
  }
  return { ...base, ...overrides }
}

let serverTemplates: Record<AskRidesMessageType, AskRidesMessageTemplate>
let serverCoordinator: AskRidesCoordinator
let serverSchedules: Record<AskRidesScheduleSlot, AskRidesScheduleEntry>
let serverSeason: "friday" | "wednesday"

function scheduleResponse(): AskRidesScheduleResponse {
  return {
    schedules: serverSchedules,
    time_window: { min_hour: 6, min_minute: 0, max_hour: 22, max_minute: 0 },
  }
}

function messagesResponse(): AskRidesMessagesResponse {
  return {
    templates: serverTemplates,
    allowed_colors: ["teal", "green", "blue", "blurple", "pink"],
    allowed_placeholders: {
      wednesday_fellowship: ["date"],
      friday_fellowship: ["date"],
      sunday_service: ["date", "ping"],
      sunday_class: ["date"],
    },
    max_reactions: 10,
  }
}

function jsonResponse(body: unknown): Response {
  return { ok: true, json: async () => body } as Response
}

beforeEach(() => {
  serverTemplates = {
    wednesday_fellowship: defaultTemplate(),
    friday_fellowship: defaultTemplate({ title: "Friday Fellowship Rides", color: "pink" }),
    sunday_service: defaultTemplate({ title: "Sunday Service Rides", color: "blue" }),
    sunday_class: defaultTemplate({ title: "Sunday Class Rides", color: "blurple" }),
  }
  serverCoordinator = { user_id: "123456789012345678", configured: true, username: "coordinator" }
  serverSchedules = {
    wednesday_reminder: { day_of_week: 0, hour: 11, minute: 0, is_customized: false, allowed_days: [0, 1] },
    fri_sun_group: { day_of_week: 2, hour: 12, minute: 0, is_customized: false, allowed_days: [0, 1, 2, 3] },
  }
  serverSeason = "friday"

  apiFetch.mockImplementation(async (endpoint: string, options?: RequestInit) => {
    if (endpoint === "/api/ask-rides/messages") return jsonResponse(messagesResponse())

    if (endpoint === "/api/ask-rides/schedule") return jsonResponse(scheduleResponse())

    if (endpoint === "/api/ask-rides/fellowship-season") return jsonResponse({ season: serverSeason })

    const scheduleMatch = endpoint.match(/^\/api\/ask-rides\/schedule\/(.+)$/)
    if (scheduleMatch && options?.method === "PUT") {
      const slot = scheduleMatch[1] as AskRidesScheduleSlot
      const body = JSON.parse(options.body as string)
      serverSchedules = {
        ...serverSchedules,
        [slot]: {
          ...body,
          is_customized: true,
          allowed_days: serverSchedules[slot].allowed_days,
        },
      }
      return jsonResponse(serverSchedules[slot])
    }

    if (scheduleMatch && options?.method === "DELETE") {
      const slot = scheduleMatch[1] as AskRidesScheduleSlot
      const defaults: Record<AskRidesScheduleSlot, AskRidesScheduleEntry> = {
        wednesday_reminder: { day_of_week: 0, hour: 11, minute: 0, is_customized: false, allowed_days: [0, 1] },
        fri_sun_group: { day_of_week: 2, hour: 12, minute: 0, is_customized: false, allowed_days: [0, 1, 2, 3] },
      }
      serverSchedules = { ...serverSchedules, [slot]: defaults[slot] }
      return jsonResponse(serverSchedules[slot])
    }

    if (endpoint === "/api/ask-rides/coordinator") {
      if (options?.method === "PUT") {
        const body = JSON.parse(options.body as string)
        serverCoordinator = { ...serverCoordinator, user_id: body.user_id }
        return jsonResponse(serverCoordinator)
      }
      return jsonResponse(serverCoordinator)
    }

    if (endpoint.startsWith("/api/ask-rides/upcoming-dates/")) {
      return jsonResponse({ dates: [{ event_date: "2026-07-08", send_date: "2026-07-07" }] })
    }

    const putMatch = endpoint.match(/^\/api\/ask-rides\/messages\/(.+)$/)
    if (putMatch && options?.method === "PUT") {
      const messageType = putMatch[1] as AskRidesMessageType
      const body = JSON.parse(options.body as string)
      serverTemplates = {
        ...serverTemplates,
        [messageType]: {
          ...body,
          is_customized: true,
          default: serverTemplates[messageType].default,
        },
      }
      return jsonResponse(serverTemplates[messageType])
    }

    if (putMatch && options?.method === "DELETE") {
      const messageType = putMatch[1] as AskRidesMessageType
      const def = serverTemplates[messageType].default
      serverTemplates = {
        ...serverTemplates,
        [messageType]: { ...def, is_customized: false, default: def },
      }
      return jsonResponse(serverTemplates[messageType])
    }

    throw new Error(`Unhandled endpoint in test: ${endpoint} ${options?.method ?? "GET"}`)
  })
})

afterEach(() => vi.clearAllMocks())

function renderEditor() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <MessageTemplatesEditor />
    </QueryClientProvider>,
  )
}

describe("MessageTemplatesEditor", () => {
  it("loads the four cards with effective templates pre-filled", async () => {
    renderEditor()

    expect(await screen.findByRole("heading", { name: "Wed. Fellowship" })).toBeInTheDocument()
    expect(screen.getByRole("heading", { name: "Friday Fellowship" })).toBeInTheDocument()
    expect(screen.getByRole("heading", { name: "Sunday Service" })).toBeInTheDocument()
    expect(screen.getByRole("heading", { name: "Sunday Class" })).toBeInTheDocument()

    expect(screen.getByDisplayValue("Wednesday Fellowship Rides")).toBeInTheDocument()
    expect(screen.queryByText("Customized")).not.toBeInTheDocument()
  })

  it("edits a card, saves, calls PUT with the right body, and shows the Customized badge", async () => {
    const user = userEvent.setup()
    renderEditor()

    const heading = await screen.findByRole("heading", { name: "Wed. Fellowship" })
    const card = heading.closest("div")!.parentElement as HTMLElement

    const titleInput = within(card).getByLabelText("Title")
    await user.clear(titleInput)
    await user.type(titleInput, "Updated Wednesday Title")

    await user.click(within(card).getByRole("button", { name: "Save" }))

    await waitFor(() =>
      expect(apiFetch).toHaveBeenCalledWith(
        "/api/ask-rides/messages/wednesday_fellowship",
        expect.objectContaining({
          method: "PUT",
          body: JSON.stringify({
            title: "Updated Wednesday Title",
            body: "Need a ride to fellowship on {date}? React below!",
            color: "teal",
            reactions: ["🪨"],
          }),
        }),
      ),
    )

    expect(await within(card).findByText("Customized")).toBeInTheDocument()
  })

  it("shows an unsaved-changes badge while editing and clears it after saving", async () => {
    const user = userEvent.setup()
    renderEditor()

    const heading = await screen.findByRole("heading", { name: "Wed. Fellowship" })
    const card = heading.closest("div")!.parentElement as HTMLElement

    // Pristine card: no badge, Save disabled.
    expect(within(card).queryByText("Unsaved changes")).not.toBeInTheDocument()
    expect(within(card).getByRole("button", { name: "Save" })).toBeDisabled()

    await user.type(within(card).getByLabelText("Title"), " edited")

    expect(within(card).getByText("Unsaved changes")).toBeInTheDocument()
    expect(within(card).getByRole("button", { name: "Save" })).toBeEnabled()

    await user.click(within(card).getByRole("button", { name: "Save" }))

    await waitFor(() => expect(within(card).queryByText("Unsaved changes")).not.toBeInTheDocument())
  })

  it("undoes local edits back to the last-saved value, not the default", async () => {
    serverTemplates.wednesday_fellowship = defaultTemplate({
      title: "Customized Wednesday Title",
      is_customized: true,
    })
    const user = userEvent.setup()
    renderEditor()

    const heading = await screen.findByRole("heading", { name: "Wed. Fellowship" })
    const card = heading.closest("div")!.parentElement as HTMLElement
    await within(card).findByDisplayValue("Customized Wednesday Title")

    // No undo button while pristine.
    expect(within(card).queryByRole("button", { name: "Undo changes" })).not.toBeInTheDocument()

    const titleInput = within(card).getByLabelText("Title")
    await user.clear(titleInput)
    await user.type(titleInput, "Scratch edit")

    await user.click(within(card).getByRole("button", { name: "Undo changes" }))

    // Back to the saved customization — not the built-in default title.
    expect(within(card).getByDisplayValue("Customized Wednesday Title")).toBeInTheDocument()
    expect(within(card).queryByText("Unsaved changes")).not.toBeInTheDocument()
    expect(apiFetch).not.toHaveBeenCalledWith(
      "/api/ask-rides/messages/wednesday_fellowship",
      expect.objectContaining({ method: "PUT" }),
    )
  })

  it("adds and removes reaction emojis and includes them in the PUT body", async () => {
    const user = userEvent.setup()
    renderEditor()

    const heading = await screen.findByRole("heading", { name: "Wed. Fellowship" })
    const card = heading.closest("div")!.parentElement as HTMLElement

    await user.type(within(card).getByLabelText("Add reaction emoji"), "🚗")
    await user.click(within(card).getByRole("button", { name: "Add" }))
    await user.click(within(card).getByRole("button", { name: "Remove reaction 🪨" }))

    await user.click(within(card).getByRole("button", { name: "Save" }))

    await waitFor(() =>
      expect(apiFetch).toHaveBeenCalledWith(
        "/api/ask-rides/messages/wednesday_fellowship",
        expect.objectContaining({
          method: "PUT",
          body: JSON.stringify({
            title: "Wednesday Fellowship Rides",
            body: "Need a ride to fellowship on {date}? React below!",
            color: "teal",
            reactions: ["🚗"],
          }),
        }),
      ),
    )
  })

  it("resets a customized card back to default after confirming", async () => {
    serverTemplates.wednesday_fellowship = defaultTemplate({
      title: "Customized Wednesday Title",
      is_customized: true,
    })
    const user = userEvent.setup()
    renderEditor()

    const heading = await screen.findByRole("heading", { name: "Wed. Fellowship" })
    const card = heading.closest("div")!.parentElement as HTMLElement
    expect(await within(card).findByText("Customized")).toBeInTheDocument()

    await user.click(within(card).getByRole("button", { name: /Reset to default/ }))
    await user.click(await screen.findByRole("button", { name: "Yes, reset" }))

    await waitFor(() =>
      expect(apiFetch).toHaveBeenCalledWith(
        "/api/ask-rides/messages/wednesday_fellowship",
        expect.objectContaining({ method: "DELETE" }),
      ),
    )

    await waitFor(() => expect(within(card).queryByText("Customized")).not.toBeInTheDocument())
    expect(within(card).getByDisplayValue("Wednesday Fellowship Rides")).toBeInTheDocument()
  })

  it("saves the main rides coordinator user ID", async () => {
    const user = userEvent.setup()
    renderEditor()

    const input = await screen.findByLabelText("Discord user ID")
    const coordinatorCard = input.closest("div")!.parentElement as HTMLElement
    await user.clear(input)
    await user.type(input, "987654321098765432")
    await user.click(within(coordinatorCard).getByRole("button", { name: "Save" }))

    await waitFor(() =>
      expect(apiFetch).toHaveBeenCalledWith(
        "/api/ask-rides/coordinator",
        expect.objectContaining({
          method: "PUT",
          body: JSON.stringify({ user_id: "987654321098765432" }),
        }),
      ),
    )
  })

  it("loads the send schedule and saves a changed day/time", async () => {
    const user = userEvent.setup()
    renderEditor()

    const heading = await screen.findByRole("heading", { name: "Wed. Fellowship Reminder" })
    const row = heading.closest("div")!.parentElement!.parentElement as HTMLElement

    const daySelect = within(row).getByLabelText("Day") as HTMLSelectElement
    expect(daySelect.value).toBe("0")
    const timeInput = within(row).getByLabelText("Time") as HTMLInputElement
    expect(timeInput.value).toBe("11:00")

    await user.selectOptions(daySelect, "1")
    await user.clear(timeInput)
    await user.type(timeInput, "09:30")

    await user.click(within(row).getByRole("button", { name: "Save" }))

    await waitFor(() =>
      expect(apiFetch).toHaveBeenCalledWith(
        "/api/ask-rides/schedule/wednesday_reminder",
        expect.objectContaining({
          method: "PUT",
          body: JSON.stringify({ day_of_week: 1, hour: 9, minute: 30 }),
        }),
      ),
    )

    expect(await within(row).findByText("Customized")).toBeInTheDocument()
  })

  it("resets a customized schedule back to default after confirming", async () => {
    serverSchedules.wednesday_reminder = {
      day_of_week: 1,
      hour: 9,
      minute: 30,
      is_customized: true,
      allowed_days: [0, 1],
    }
    const user = userEvent.setup()
    renderEditor()

    const heading = await screen.findByRole("heading", { name: "Wed. Fellowship Reminder" })
    const row = heading.closest("div")!.parentElement!.parentElement as HTMLElement
    expect(await within(row).findByText("Customized")).toBeInTheDocument()

    await user.click(within(row).getByRole("button", { name: /Reset to default/ }))
    await user.click(await screen.findByRole("button", { name: "Yes, reset" }))

    await waitFor(() =>
      expect(apiFetch).toHaveBeenCalledWith(
        "/api/ask-rides/schedule/wednesday_reminder",
        expect.objectContaining({ method: "DELETE" }),
      ),
    )

    await waitFor(() => expect(within(row).queryByText("Customized")).not.toBeInTheDocument())
    expect((within(row).getByLabelText("Day") as HTMLSelectElement).value).toBe("0")
    expect((within(row).getByLabelText("Time") as HTMLInputElement).value).toBe("11:00")
  })

  it("marks the Wednesday reminder inactive when Friday season is active, not the Fri/Sun row", async () => {
    serverSeason = "friday"
    renderEditor()

    const wedHeading = await screen.findByRole("heading", { name: "Wed. Fellowship Reminder" })
    const wedRow = wedHeading.closest("div")!.parentElement!.parentElement as HTMLElement
    expect(await within(wedRow).findByText("Inactive this season")).toBeInTheDocument()

    const friSunHeading = screen.getByRole("heading", { name: "Friday/Sunday Group Send" })
    const friSunRow = friSunHeading.closest("div")!.parentElement!.parentElement as HTMLElement
    expect(within(friSunRow).queryByText("Inactive this season")).not.toBeInTheDocument()
  })

  it("does not mark the Wednesday reminder inactive when Wednesday season is active", async () => {
    serverSeason = "wednesday"
    renderEditor()

    const wedHeading = await screen.findByRole("heading", { name: "Wed. Fellowship Reminder" })
    const wedRow = wedHeading.closest("div")!.parentElement!.parentElement as HTMLElement

    await waitFor(() => expect(within(wedRow).getByLabelText("Day")).toBeInTheDocument())
    expect(within(wedRow).queryByText("Inactive this season")).not.toBeInTheDocument()
  })
})
