import type { ReactNode } from 'react'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { SettingsSection } from './SettingsSection'

// Use a native select to exercise the settings workflow independently of Radix's pointer API.
vi.mock('../ui/select', () => ({
    Select: ({ children, value, onValueChange, disabled }: {
        children: ReactNode; value: string; onValueChange: (value: string) => void; disabled: boolean
    }) => <select aria-label="Pickup spot" value={value} disabled={disabled} onChange={(e) => onValueChange(e.target.value)}>{children}</select>,
    SelectTrigger: () => null,
    SelectValue: () => null,
    SelectContent: ({ children }: { children: ReactNode }) => <>{children}</>,
    SelectItem: ({ children, value }: { children: ReactNode; value: string }) => <option value={value}>{children}</option>,
}))

function setup(onSetMapping = vi.fn().mockResolvedValue(undefined), onAnnounce = vi.fn().mockResolvedValue(undefined)) {
    const onSaveAdjustment = vi.fn()
    render(<SettingsSection
        pickupAdjustment={1}
        livingMappings={[{ living_location: 'Muir', pickup_location_id: 1 }]}
        locations={[1, 2].map((id) => ({
            id, name: id === 1 ? 'Muir tennis courts' : 'Innovation',
            latitude: 32.88, longitude: -117.24,
            is_active: true, is_seeded: true, minutes_from_start: null, minutes_to_end: null,
        }))}
        savingAdjustment={false} savingMapping={false}
        onSaveAdjustment={onSaveAdjustment} onSetMapping={onSetMapping} onAnnounce={onAnnounce}
    />)
    return { onSetMapping, onAnnounce, onSaveAdjustment }
}

async function changeSpot() {
    fireEvent.change(screen.getByRole('combobox'), { target: { value: '2' } })
    await screen.findByRole('dialog')
}

describe('Pickup change announcements', () => {
    it('saves the spot first and sends only after Yes', async () => {
        const { onSetMapping, onAnnounce } = setup()
        await changeSpot()
        expect(onSetMapping).toHaveBeenCalledWith('Muir', 2)
        expect(onAnnounce).not.toHaveBeenCalled()
        expect(screen.getByRole('link', { name: 'View pickup spot on Google Maps' })).toHaveAttribute('href', 'https://www.google.com/maps/search/?api=1&query=32.88,-117.24')
        expect(screen.getByText(/Riders living in Muir will now be picked up at Innovation/)).toBeInTheDocument()
        await userEvent.click(screen.getByRole('button', { name: 'Yes, send announcement' }))
        await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
        expect(onAnnounce).toHaveBeenCalledExactlyOnceWith('Muir', 2)
    })

    it('keeps the saved mapping without sending when declined', async () => {
        const { onSetMapping, onAnnounce } = setup()
        await changeSpot()
        await userEvent.click(screen.getByRole('button', { name: 'No, thanks' }))
        expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
        expect(onSetMapping).toHaveBeenCalledOnce()
        expect(onAnnounce).not.toHaveBeenCalled()
    })

    it('does not prompt when saving fails', async () => {
        const { onSetMapping, onAnnounce } = setup(vi.fn().mockRejectedValue(new Error('Save failed')))
        fireEvent.change(screen.getByRole('combobox'), { target: { value: '2' } })
        await waitFor(() => expect(onSetMapping).toHaveBeenCalledOnce())
        expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
        expect(onAnnounce).not.toHaveBeenCalled()
    })

    it('allows retry after an announcement failure', async () => {
        const announce = vi.fn().mockRejectedValueOnce(new Error('Unavailable')).mockResolvedValue(undefined)
        setup(undefined, announce)
        await changeSpot()
        await userEvent.click(screen.getByRole('button', { name: 'Yes, send announcement' }))
        expect(await screen.findByRole('alert')).toHaveTextContent('Your pickup change is saved')
        await userEvent.click(screen.getByRole('button', { name: 'Yes, send announcement' }))
        await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
        expect(announce).toHaveBeenCalledTimes(2)
    })

    it('saves pickup adjustment without prompting or sending', async () => {
        const { onSaveAdjustment, onAnnounce } = setup()
        fireEvent.change(screen.getByLabelText('Pickup adjustment'), { target: { value: '3' } })
        await userEvent.click(screen.getByRole('button', { name: 'Save' }))
        expect(onSaveAdjustment).toHaveBeenCalledWith(3)
        expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
        expect(onAnnounce).not.toHaveBeenCalled()
    })
})
