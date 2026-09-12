import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import type { PickupInfoOptions, PickupInfoPerson } from '../../types'

// ── Mock the network boundary, not auth ──────────────────────────────────
// PickupInfoTable is presentational (it takes people/options as props), but we
// mock `lib/api` anyway so importing it anywhere in the tree never triggers
// a real fetch, mirroring the AskRidesDashboard tests.
const { apiFetch } = vi.hoisted(() => ({ apiFetch: vi.fn() }))
vi.mock('@/lib/api', () => ({ apiFetch, ApiError: class ApiError extends Error {} }))

import { PickupInfoTable } from './PickupInfoTable'

function person(overrides: Partial<PickupInfoPerson> = {}): PickupInfoPerson {
    return {
        id: 1,
        name: 'Jane Doe',
        discord_username: 'janedoe',
        discord_user_id: '123456789',
        year: 'Sophomore',
        location: 'Pepper Canyon West',
        updated_at: '2026-09-10T12:00:00Z',
        ...overrides,
    }
}

const options: PickupInfoOptions = {
    years: ['Freshman', 'Sophomore', 'Junior', 'Senior'],
    locations: ['Pepper Canyon West', 'Muir'],
}

function renderTable(
    people: PickupInfoPerson[],
    opts: PickupInfoOptions | undefined = options,
    overrides: { onDeleteAll?: () => void } = {}
) {
    return render(
        <PickupInfoTable
            people={people}
            options={opts}
            isLoading={false}
            onEdit={vi.fn()}
            onDelete={vi.fn()}
            onBulkDelete={vi.fn()}
            onDeleteAll={overrides.onDeleteAll ?? vi.fn()}
            onAdd={vi.fn()}
        />
    )
}

describe('PickupInfoTable', () => {
    it('renders every person', () => {
        renderTable([person(), person({ id: 2, name: 'John Smith', discord_username: 'jsmith' })])

        expect(screen.getByText('Jane Doe')).toBeInTheDocument()
        expect(screen.getByText('John Smith')).toBeInTheDocument()
    })

    it('shows an empty state when there is no pickup info', () => {
        renderTable([])

        expect(screen.getByText('No pickup info yet.')).toBeInTheDocument()
    })

    it('filters by name and by discord username', async () => {
        const user = userEvent.setup()
        renderTable([person(), person({ id: 2, name: 'John Smith', discord_username: 'jsmith' })])

        const search = screen.getByPlaceholderText('Search by name or username…')

        await user.type(search, 'jsmith')
        expect(screen.queryByText('Jane Doe')).not.toBeInTheDocument()
        expect(screen.getByText('John Smith')).toBeInTheDocument()

        await user.clear(search)
        await user.type(search, 'jane')
        expect(screen.getByText('Jane Doe')).toBeInTheDocument()
        expect(screen.queryByText('John Smith')).not.toBeInTheDocument()
    })

    it('shows no matches when the search has no hits', async () => {
        const user = userEvent.setup()
        renderTable([person()])

        await user.type(screen.getByPlaceholderText('Search by name or username…'), 'nobody')
        expect(screen.getByText('No matches for your search.')).toBeInTheDocument()
    })

    it('flags rows whose year is not a valid option', () => {
        renderTable([
            person(),
            person({ id: 2, name: 'Old Data', year: 'Grad Student', location: null }),
        ])

        const oldDataRow = screen.getByText('Old Data').closest('tr')
        expect(oldDataRow).not.toBeNull()
        expect(oldDataRow && screen.getByText('Needs fix').closest('tr')).toBe(oldDataRow)

        const janeRow = screen.getByText('Jane Doe').closest('tr')
        expect(janeRow?.textContent).not.toContain('Needs fix')
    })

    it('calls onDeleteAll when the delete all button is clicked', async () => {
        const onDeleteAll = vi.fn()
        const user = userEvent.setup()
        renderTable([person()], options, { onDeleteAll })

        await user.click(screen.getByRole('button', { name: /delete all/i }))
        expect(onDeleteAll).toHaveBeenCalledTimes(1)
    })

    it('hides the delete all button when there is no pickup info', () => {
        renderTable([])

        expect(screen.queryByRole('button', { name: /delete all/i })).toBeNull()
    })

    it('does not flag an off-campus location', () => {
        renderTable([person({ id: 3, name: 'Off Campus', location: 'Costa Verde' })])

        const row = screen.getByText('Off Campus').closest('tr')
        expect(row?.textContent).toContain('Costa Verde')
        expect(row?.textContent).not.toContain('Needs fix')
    })

    it('tracks selection count and shows the bulk delete button', async () => {
        const user = userEvent.setup()
        renderTable([person(), person({ id: 2, name: 'John Smith', discord_username: 'jsmith' })])

        expect(screen.queryByText(/Delete selected/)).not.toBeInTheDocument()

        await user.click(screen.getByLabelText('Select Jane Doe'))
        expect(screen.getByText('Delete selected (1)')).toBeInTheDocument()

        await user.click(screen.getByLabelText('Select John Smith'))
        expect(screen.getByText('Delete selected (2)')).toBeInTheDocument()

        await user.click(screen.getByLabelText('Select Jane Doe'))
        expect(screen.getByText('Delete selected (1)')).toBeInTheDocument()
    })
})
