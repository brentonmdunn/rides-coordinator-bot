import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, expect, it, vi } from 'vitest'

const { apiFetch } = vi.hoisted(() => ({ apiFetch: vi.fn() }))
vi.mock('../lib/api', () => ({ apiFetch }))
import RideEvents from './RideEvents'

const detail = {
    id: 1, event_date: '2099-10-25', message_type: 'sunday_service',
    freshness: { last_reconciled_at: null, is_stale: true, errors: [], source_count: 1 },
    requests: [{ id: 4, name: 'Alice', location: 'ERC', source: 'discord', details: 'Return early', needs_review: true, pickup: true, return_preference: 'custom' }],
    driver_offers: [{ id: 7, discord_user_id: '99', discord_username: 'driver', availability: 'available', capacity: 4, directions: ['pickup', 'return'] }],
    assignments: [],
}

beforeEach(() => {
    apiFetch.mockReset()
    apiFetch.mockImplementation(async (endpoint: string, options?: RequestInit) => {
        if (endpoint === '/api/me') return { json: async () => ({ role: 'ride_coordinator' }) }
        if (endpoint.startsWith('/api/ride-events?')) return { json: async () => [detail] }
        if (!options?.method) return { json: async () => detail }
        return { json: async () => ({ success: true }) }
    })
})

function mount() {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
    render(<MemoryRouter><QueryClientProvider client={client}><RideEvents /></QueryClientProvider></MemoryRouter>)
}

it('shows custom requests and saves assignments using stable IDs', async () => {
    mount()
    const user = userEvent.setup()
    expect(await screen.findByText('Return early')).toBeInTheDocument()
    expect(screen.getByText(/Waiting for a complete sync/)).toBeInTheDocument()
    await user.selectOptions(screen.getByLabelText('Alice pickup driver'), '7')
    await user.click(screen.getByRole('button', { name: 'Save assignments' }))
    await waitFor(() => expect(apiFetch).toHaveBeenCalledWith('/api/ride-events/1/assignments', expect.objectContaining({
        method: 'PUT', body: JSON.stringify({ assignments: [{ request_id: 4, direction: 'pickup', driver_offer_id: 7 }] }),
    })))
})

it('retains the draft and displays capacity errors returned by the server', async () => {
    const original = apiFetch.getMockImplementation()!
    apiFetch.mockImplementation(async (endpoint: string, options?: RequestInit) => {
        if (endpoint.endsWith('/assignments')) throw new Error('Assignment exceeds driver passenger capacity')
        return original(endpoint, options)
    })
    mount()
    const user = userEvent.setup()
    await screen.findByText('Return early')
    await user.selectOptions(screen.getByLabelText('Alice pickup driver'), '7')
    await user.click(screen.getByRole('button', { name: 'Save assignments' }))
    expect(await screen.findByText(/Assignment exceeds/)).toBeInTheDocument()
    expect(screen.getByLabelText('Alice pickup driver')).toHaveValue('7')
})
