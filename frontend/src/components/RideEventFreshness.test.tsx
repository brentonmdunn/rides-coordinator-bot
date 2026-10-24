import { act, render, screen } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import RideEventFreshness from './RideEventFreshness'

afterEach(() => vi.useRealTimers())

it('marks a previously fresh snapshot stale as time passes', () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-10-21T19:00:00Z'))
    render(<RideEventFreshness freshness={{ last_reconciled_at: '2026-10-21T19:00:00Z', is_stale: false, errors: [], source_count: 1 }} />)
    expect(screen.queryByText(/may be out of date/)).not.toBeInTheDocument()
    act(() => vi.advanceTimersByTime(16 * 60_000))
    expect(screen.getByText(/may be out of date/)).toBeInTheDocument()
})

it('distinguishes an incomplete sync from a manual-only event', () => {
    const { rerender } = render(<RideEventFreshness freshness={{ last_reconciled_at: null, is_stale: true, errors: ['Could not refresh Discord reactions'], source_count: 1 }} />)
    expect(screen.getByText(/Waiting for a complete sync/)).toBeInTheDocument()
    expect(screen.getByText(/Could not refresh/)).toBeInTheDocument()
    rerender(<RideEventFreshness freshness={{ last_reconciled_at: null, is_stale: false, errors: [], source_count: 0 }} />)
    expect(screen.getByText(/No active Discord source/)).toBeInTheDocument()
    expect(screen.queryByText(/may be out of date/)).not.toBeInTheDocument()
})
