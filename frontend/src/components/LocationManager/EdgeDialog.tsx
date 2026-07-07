/**
 * EdgeDialog.tsx
 *
 * Minutes prompt for a travel-time edge between two named locations. Used
 * both when connecting two markers on the map (create/upsert) and when
 * editing an existing edge (edit + delete). The body is keyed on the pair so
 * fields initialize from props on every open (no state-syncing effects).
 */

import { useState } from 'react'
import { Button } from '../ui/button'
import { Input } from '../ui/input'
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from '../ui/dialog'

export interface EdgeDialogState {
    locationAId: number
    locationBId: number
    locationAName: string
    locationBName: string
    /** Prefilled minutes when the pair already has an edge. */
    minutes: number | null
    /** Set when editing an existing edge — enables the Delete button. */
    edgeId: number | null
}

interface EdgeDialogProps {
    state: EdgeDialogState | null
    submitting: boolean
    onSave: (minutes: number) => void
    onDelete: (edgeId: number) => void
    onClose: () => void
}

function EdgeDialogBody({
    state,
    submitting,
    onSave,
    onDelete,
    onClose,
}: {
    state: EdgeDialogState
    submitting: boolean
    onSave: (minutes: number) => void
    onDelete: (edgeId: number) => void
    onClose: () => void
}) {
    const [minutes, setMinutes] = useState(
        state.minutes != null ? String(state.minutes) : ''
    )
    const [error, setError] = useState('')

    const handleSave = () => {
        const value = Number(minutes.trim())
        if (minutes.trim() === '' || !Number.isInteger(value) || value <= 0) {
            setError('Minutes must be a positive whole number')
            return
        }
        onSave(value)
    }

    return (
        <>
            <DialogHeader>
                <DialogTitle>
                    {state.edgeId != null ? 'Edit travel time' : 'New travel time'}
                </DialogTitle>
                <DialogDescription>
                    {state.locationAName} ↔ {state.locationBName}
                </DialogDescription>
            </DialogHeader>

            <div className="space-y-1.5">
                <label htmlFor="edge-minutes" className="text-sm font-medium text-foreground">
                    Minutes
                </label>
                <Input
                    id="edge-minutes"
                    inputMode="numeric"
                    value={minutes}
                    onChange={(e) => setMinutes(e.target.value)}
                    onKeyDown={(e) => { if (e.key === 'Enter') handleSave() }}
                    placeholder="e.g. 3"
                    autoFocus
                />
                {error && <p className="text-sm text-destructive-text">{error}</p>}
            </div>

            <DialogFooter className="gap-2 sm:justify-between">
                {state.edgeId != null ? (
                    <Button
                        variant="destructive"
                        onClick={() => onDelete(state.edgeId as number)}
                        disabled={submitting}
                    >
                        Delete
                    </Button>
                ) : (
                    <span />
                )}
                <div className="flex gap-2">
                    <Button variant="outline" onClick={onClose}>
                        Cancel
                    </Button>
                    <Button onClick={handleSave} disabled={submitting}>
                        {submitting ? 'Saving…' : 'Save'}
                    </Button>
                </div>
            </DialogFooter>
        </>
    )
}

export function EdgeDialog({ state, submitting, onSave, onDelete, onClose }: EdgeDialogProps) {
    return (
        <Dialog open={state != null} onOpenChange={(open) => { if (!open) onClose() }}>
            <DialogContent className="sm:max-w-sm">
                {state && (
                    <EdgeDialogBody
                        key={`${state.locationAId}-${state.locationBId}`}
                        state={state}
                        submitting={submitting}
                        onSave={onSave}
                        onDelete={onDelete}
                        onClose={onClose}
                    />
                )}
            </DialogContent>
        </Dialog>
    )
}
