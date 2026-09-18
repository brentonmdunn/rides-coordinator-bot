import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { FellowshipSeason, LateReactionWindows, PickupSummaryEntry, PickupSummarySlot } from '@/types'

// ── Mock the network boundary, not auth ──────────────────────────────────
const { apiFetch, ApiError } = vi.hoisted(() => {
    class ApiError extends Error {
        status: number
        detail: string
        constructor(status: number, detail: string) {
            super(detail)
            this.name = 'ApiError'
            this.status = status
            this.detail = detail
        }
    }
    return { apiFetch: vi.fn(), ApiError }
})
vi.mock('@/lib/api', () => ({ apiFetch, ApiError, getApiUrl: (endpoint: string) => endpoint }))

const { toastWarning } = vi.hoisted(() => ({ toastWarning: vi.fn() }))
vi.mock('sonner', () => ({
    toast: { warning: toastWarning, success: vi.fn(), error: vi.fn() },
}))

import SiteSettingsDialog from './SiteSettingsDialog'

// ── Tiny in-memory "server" ───────────────────────────────────────────────

let serverSeason: FellowshipSeason
let serverLateReactionWindows: LateReactionWindows
let serverPickupSummaries: Record<PickupSummarySlot, PickupSummaryEntry>

function defaultEntry(overrides: Partial<PickupSummaryEntry> = {}): PickupSummaryEntry {
    return {
        enabled: true,
        day_of_week: 4,
        hour: 11,
        minute: 0,
        is_customized: false,
        allowed_days: [0, 1, 2, 3, 4],
        default: { day_of_week: 4, hour: 11, minute: 0 },
        ...overrides,
    }
}

function jsonResponse(body: unknown): Response {
    return { ok: true, json: async () => body } as Response
}

beforeEach(() => {
    serverSeason = 'friday'
    serverLateReactionWindows = {
        wednesday: { start_day: 'Wednesday', start_time: '00:00', end_day: 'Thursday', end_time: '12:00' },
        friday: { start_day: 'Friday', start_time: '00:00', end_day: 'Saturday', end_time: '12:00' },
        sunday: { start_day: 'Sunday', start_time: '00:00', end_day: 'Sunday', end_time: '18:00' },
    }
    serverPickupSummaries = {
        friday: defaultEntry(),
        sunday: defaultEntry({ day_of_week: 5, hour: 16, minute: 0, allowed_days: [0, 1, 2, 3, 4, 5], default: { day_of_week: 5, hour: 16, minute: 0 } }),
    }

    apiFetch.mockImplementation(async (endpoint: string, options?: RequestInit) => {
        if (endpoint === '/api/ask-rides/fellowship-season') return jsonResponse({ season: serverSeason })
        if (endpoint === '/api/ask-rides/late-reaction-windows') return jsonResponse(serverLateReactionWindows)

        if (endpoint === '/api/ask-rides/pickup-summaries') {
            return jsonResponse({
                summaries: serverPickupSummaries,
                time_window: { min_hour: 6, min_minute: 0, max_hour: 22, max_minute: 0 },
            })
        }

        const match = endpoint.match(/^\/api\/ask-rides\/pickup-summaries\/(.+)$/)
        if (match && options?.method === 'PUT') {
            const slot = match[1] as PickupSummarySlot
            const body = JSON.parse(options.body as string)
            serverPickupSummaries = {
                ...serverPickupSummaries,
                [slot]: {
                    ...body,
                    is_customized: true,
                    allowed_days: serverPickupSummaries[slot].allowed_days,
                    default: serverPickupSummaries[slot].default,
                },
            }
            return jsonResponse(serverPickupSummaries[slot])
        }

        if (match && options?.method === 'DELETE') {
            const slot = match[1] as PickupSummarySlot
            const def = serverPickupSummaries[slot].default!
            serverPickupSummaries = {
                ...serverPickupSummaries,
                [slot]: {
                    ...def,
                    enabled: true,
                    is_customized: false,
                    allowed_days: serverPickupSummaries[slot].allowed_days,
                    default: def,
                },
            }
            return jsonResponse(serverPickupSummaries[slot])
        }

        throw new Error(`Unhandled endpoint in test: ${endpoint} ${options?.method ?? 'GET'}`)
    })
})

afterEach(() => vi.clearAllMocks())

function renderDialog(canManage = true) {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    return render(
        <QueryClientProvider client={queryClient}>
            <SiteSettingsDialog open={true} onOpenChange={() => {}} canManage={canManage} />
        </QueryClientProvider>,
    )
}

describe('SiteSettingsDialog - Pickup summaries', () => {
    it('renders both rows with their values', async () => {
        renderDialog()

        expect(await screen.findByText('Friday fellowship pickups')).toBeInTheDocument()
        expect(screen.getByText('Sunday service pickups')).toBeInTheDocument()

        const fridayRow = screen.getByText('Friday fellowship pickups').closest('div')!.parentElement as HTMLElement
        expect((within(fridayRow).getByLabelText('Day') as HTMLSelectElement).value).toBe('4')
        expect((within(fridayRow).getByLabelText('Time') as HTMLInputElement).value).toBe('11:00')
        expect(within(fridayRow).getByText('Default: Fri 11:00 AM')).toBeInTheDocument()

        const sundayRow = screen.getByText('Sunday service pickups').closest('div')!.parentElement as HTMLElement
        expect((within(sundayRow).getByLabelText('Day') as HTMLSelectElement).value).toBe('5')
        expect((within(sundayRow).getByLabelText('Time') as HTMLInputElement).value).toBe('16:00')
    })

    it('does not show a Reset button until customized', async () => {
        renderDialog()
        await screen.findByText('Friday fellowship pickups')
        const fridayRow = screen.getByText('Friday fellowship pickups').closest('div')!.parentElement as HTMLElement
        expect(within(fridayRow).queryByRole('button', { name: /Reset to default/ })).not.toBeInTheDocument()
    })

    it('toggling the switch sends a PUT with the full entry', async () => {
        const user = userEvent.setup()
        renderDialog()

        await screen.findByText('Friday fellowship pickups')
        const toggle = screen.getByLabelText('Friday fellowship pickups enabled')
        await user.click(toggle)

        await waitFor(() =>
            expect(apiFetch).toHaveBeenCalledWith(
                '/api/ask-rides/pickup-summaries/friday',
                expect.objectContaining({
                    method: 'PUT',
                    body: JSON.stringify({ enabled: false, day_of_week: 4, hour: 11, minute: 0 }),
                }),
            ),
        )
    })

    it('changing the day sends a PUT with the full entry', async () => {
        const user = userEvent.setup()
        renderDialog()

        await screen.findByText('Friday fellowship pickups')
        const fridayRow = screen.getByText('Friday fellowship pickups').closest('div')!.parentElement as HTMLElement
        const daySelect = within(fridayRow).getByLabelText('Day') as HTMLSelectElement

        await user.selectOptions(daySelect, '2')

        await waitFor(() =>
            expect(apiFetch).toHaveBeenCalledWith(
                '/api/ask-rides/pickup-summaries/friday',
                expect.objectContaining({
                    method: 'PUT',
                    body: JSON.stringify({ enabled: true, day_of_week: 2, hour: 11, minute: 0 }),
                }),
            ),
        )

        expect(await within(fridayRow).findByRole('button', { name: /Reset to default/ })).toBeInTheDocument()
    })

    it('changing the time sends a PUT with the full entry only on blur', async () => {
        renderDialog()

        await screen.findByText('Sunday service pickups')
        const sundayRow = screen.getByText('Sunday service pickups').closest('div')!.parentElement as HTMLElement
        const timeInput = within(sundayRow).getByLabelText('Time') as HTMLInputElement

        // fireEvent for <input type="time"> is more reliable than userEvent.type here.
        const { fireEvent } = await import('@testing-library/react')
        fireEvent.change(timeInput, { target: { value: '18:30' } })
        expect(apiFetch).not.toHaveBeenCalledWith(
            '/api/ask-rides/pickup-summaries/sunday',
            expect.objectContaining({ method: 'PUT' }),
        )
        fireEvent.blur(timeInput)

        await waitFor(() =>
            expect(apiFetch).toHaveBeenCalledWith(
                '/api/ask-rides/pickup-summaries/sunday',
                expect.objectContaining({
                    method: 'PUT',
                    body: JSON.stringify({ enabled: true, day_of_week: 5, hour: 18, minute: 30 }),
                }),
            ),
        )
    })

    it('shows Reset to default only when customized, and reset sends a DELETE', async () => {
        serverPickupSummaries.friday = defaultEntry({ day_of_week: 2, is_customized: true })
        const user = userEvent.setup()
        renderDialog()

        await screen.findByText('Friday fellowship pickups')
        const fridayRow = screen.getByText('Friday fellowship pickups').closest('div')!.parentElement as HTMLElement

        const resetButton = await within(fridayRow).findByRole('button', { name: /Reset to default/ })
        await user.click(resetButton)

        await waitFor(() =>
            expect(apiFetch).toHaveBeenCalledWith(
                '/api/ask-rides/pickup-summaries/friday',
                expect.objectContaining({ method: 'DELETE' }),
            ),
        )

        await waitFor(() =>
            expect(within(fridayRow).queryByRole('button', { name: /Reset to default/ })).not.toBeInTheDocument(),
        )
    })

    it('shows a warning toast when the PUT response includes one', async () => {
        serverPickupSummaries.friday = defaultEntry()
        apiFetch.mockImplementation(async (endpoint: string, options?: RequestInit) => {
            if (endpoint === '/api/ask-rides/fellowship-season') return jsonResponse({ season: serverSeason })
            if (endpoint === '/api/ask-rides/late-reaction-windows') return jsonResponse(serverLateReactionWindows)
            if (endpoint === '/api/ask-rides/pickup-summaries') {
                return jsonResponse({
                    summaries: serverPickupSummaries,
                    time_window: { min_hour: 6, min_minute: 0, max_hour: 22, max_minute: 0 },
                })
            }
            if (endpoint === '/api/ask-rides/pickup-summaries/friday' && options?.method === 'PUT') {
                return jsonResponse({
                    ...defaultEntry(),
                    enabled: false,
                    is_customized: true,
                    warning: 'Saved, but will not take effect until the bot reconnects.',
                })
            }
            throw new Error(`Unhandled endpoint in test: ${endpoint}`)
        })

        const user = userEvent.setup()
        renderDialog()

        await screen.findByText('Friday fellowship pickups')
        const toggle = screen.getByLabelText('Friday fellowship pickups enabled')
        await user.click(toggle)

        await waitFor(() =>
            expect(toastWarning).toHaveBeenCalledWith('Saved, but will not take effect until the bot reconnects.'),
        )
    })

    it('shows the server error message on a validation failure', async () => {
        apiFetch.mockImplementation(async (endpoint: string, options?: RequestInit) => {
            if (endpoint === '/api/ask-rides/fellowship-season') return jsonResponse({ season: serverSeason })
            if (endpoint === '/api/ask-rides/late-reaction-windows') return jsonResponse(serverLateReactionWindows)
            if (endpoint === '/api/ask-rides/pickup-summaries') {
                return jsonResponse({
                    summaries: serverPickupSummaries,
                    time_window: { min_hour: 6, min_minute: 0, max_hour: 22, max_minute: 0 },
                })
            }
            if (endpoint === '/api/ask-rides/pickup-summaries/friday' && options?.method === 'PUT') {
                throw new ApiError(422, 'hour must be between 6 and 22')
            }
            throw new Error(`Unhandled endpoint in test: ${endpoint}`)
        })

        const user = userEvent.setup()
        renderDialog()

        await screen.findByText('Friday fellowship pickups')
        const toggle = screen.getByLabelText('Friday fellowship pickups enabled')
        await user.click(toggle)

        expect(await screen.findByText('hour must be between 6 and 22')).toBeInTheDocument()
    })

    it('disables all controls when canManage is false', async () => {
        renderDialog(false)

        await screen.findByText('Friday fellowship pickups')
        expect(screen.getByLabelText('Friday fellowship pickups enabled')).toBeDisabled()
        expect(screen.getByLabelText('Sunday service pickups enabled')).toBeDisabled()

        const fridayRow = screen.getByText('Friday fellowship pickups').closest('div')!.parentElement as HTMLElement
        expect(within(fridayRow).getByLabelText('Day')).toBeDisabled()
        expect(within(fridayRow).getByLabelText('Time')).toBeDisabled()
    })
})
