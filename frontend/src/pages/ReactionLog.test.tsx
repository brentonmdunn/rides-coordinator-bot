import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, expect, it, vi } from 'vitest'

const { apiFetch } = vi.hoisted(() => ({ apiFetch: vi.fn() }))
vi.mock('../lib/api', () => ({ apiFetch }))
vi.mock('../hooks/useReactionStream', () => ({ useReactionStream: () => ({ streamError: false }) }))
vi.mock('../components/mode-toggle', () => ({ ModeToggle: () => null }))
import ReactionLog from './ReactionLog'

beforeEach(() => {
    apiFetch.mockReset()
    apiFetch.mockResolvedValue({ json: async () => ({ rides: [] }) })
})

function renderLog(path = '/reaction-log') {
    render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
        <MemoryRouter initialEntries={[path]}><ReactionLog /></MemoryRouter>
    </QueryClientProvider>)
}

it('searches all history for remaining reactions and clears the search', async () => {
    const user = userEvent.setup()
    renderLog()
    await user.type(screen.getByLabelText('Search a person'), 'Jane')
    await waitFor(() => expect(apiFetch).toHaveBeenCalledWith('/api/reaction-log?search=Jane&remaining_only=true'))
    expect(screen.getByLabelText('Only reactions still remaining')).toBeChecked()
    expect(screen.getByLabelText('From')).toHaveValue('')
    await user.click(screen.getByRole('button', { name: 'Clear filters' }))
    expect(screen.getByLabelText('Search a person')).toHaveValue('')
    expect(screen.getByLabelText('Only reactions still remaining')).not.toBeChecked()
})

it('opens the exact person from pickup info without a date limit', async () => {
    renderLog('/reaction-log?person_id=42&name=Jane+Doe')
    await waitFor(() => expect(apiFetch).toHaveBeenCalledWith('/api/reaction-log?person_id=42&remaining_only=true'))
    expect(screen.getByText('Ride history for Jane Doe')).toBeInTheDocument()
})

it('shows ride dates and counts each returned ride once', async () => {
    apiFetch.mockResolvedValue({ json: async () => ({ rides: [{
        message_id: '1', ride_type: 'friday', ride_date: '2026-10-02', label: 'Friday · October 2, 2026',
        events: [{ id: 1, discord_username: 'jane', display_name: 'Jane', emoji: '❤️', action: 'add', occurred_at: '2026-10-01T12:00:00Z' }],
    }] }) })
    renderLog('/reaction-log?person_id=42&name=Jane')
    expect(await screen.findByText('Friday · October 2, 2026')).toBeInTheDocument()
    expect(screen.getByText('1 ride with remaining reactions')).toBeInTheDocument()
})
