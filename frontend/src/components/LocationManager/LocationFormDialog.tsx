/**
 * LocationFormDialog.tsx
 *
 * Create/edit dialog for a pickup location — name, coordinates and the
 * optional from-start / to-end minutes. Create mode can be pre-filled with
 * coordinates from a map click. The form body is keyed on the dialog state
 * so fields initialize from props on every open (no state-syncing effects).
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
import type { ManagedPickupLocation } from '../../types'
import type { LocationInput } from './useLocationManager'

export interface LocationFormState {
    /** Existing location when editing; null when creating. */
    location: ManagedPickupLocation | null
    /** Pre-filled coordinates from a map click (create mode). */
    prefill?: { latitude: number; longitude: number }
}

interface LocationFormDialogProps {
    state: LocationFormState | null
    submitting: boolean
    onSubmit: (input: LocationInput) => void
    onClose: () => void
}

interface FieldErrors {
    name?: string
    latitude?: string
    longitude?: string
    minutes?: string
}

function parseOptionalMinutes(raw: string): number | null | 'invalid' {
    const trimmed = raw.trim()
    if (trimmed === '') return null
    const value = Number(trimmed)
    if (!Number.isInteger(value) || value <= 0) return 'invalid'
    return value
}

function LocationFormBody({
    state,
    submitting,
    onSubmit,
    onClose,
}: {
    state: LocationFormState
    submitting: boolean
    onSubmit: (input: LocationInput) => void
    onClose: () => void
}) {
    const [name, setName] = useState(state.location?.name ?? '')
    const [latitude, setLatitude] = useState(
        String(state.location?.latitude ?? state.prefill?.latitude.toFixed(6) ?? '')
    )
    const [longitude, setLongitude] = useState(
        String(state.location?.longitude ?? state.prefill?.longitude.toFixed(6) ?? '')
    )
    const [minutesFromStart, setMinutesFromStart] = useState(
        state.location?.minutes_from_start != null
            ? String(state.location.minutes_from_start)
            : ''
    )
    const [minutesToEnd, setMinutesToEnd] = useState(
        state.location?.minutes_to_end != null ? String(state.location.minutes_to_end) : ''
    )
    const [errors, setErrors] = useState<FieldErrors>({})

    const isEdit = state.location != null

    const handleSubmit = () => {
        const nextErrors: FieldErrors = {}

        const trimmedName = name.trim()
        if (!trimmedName) nextErrors.name = 'Name is required'

        const lat = Number(latitude)
        if (latitude.trim() === '' || Number.isNaN(lat) || lat < -90 || lat > 90) {
            nextErrors.latitude = 'Latitude must be between -90 and 90'
        }

        const lng = Number(longitude)
        if (longitude.trim() === '' || Number.isNaN(lng) || lng < -180 || lng > 180) {
            nextErrors.longitude = 'Longitude must be between -180 and 180'
        }

        const fromStart = parseOptionalMinutes(minutesFromStart)
        const toEnd = parseOptionalMinutes(minutesToEnd)
        if (fromStart === 'invalid' || toEnd === 'invalid') {
            nextErrors.minutes = 'Minutes must be a positive whole number (or blank)'
        }

        setErrors(nextErrors)
        if (Object.keys(nextErrors).length > 0) return
        if (fromStart === 'invalid' || toEnd === 'invalid') return

        onSubmit({
            name: trimmedName,
            latitude: lat,
            longitude: lng,
            minutes_from_start: fromStart,
            minutes_to_end: toEnd,
        })
    }

    return (
        <>
            <DialogHeader>
                <DialogTitle>{isEdit ? 'Edit location' : 'New location'}</DialogTitle>
                <DialogDescription>
                    {isEdit
                        ? 'Update the name, coordinates or destination times.'
                        : 'Add a pickup location by name and GPS coordinates.'}
                </DialogDescription>
            </DialogHeader>

            <div className="space-y-4">
                <div className="space-y-1.5">
                    <label htmlFor="loc-name" className="text-sm font-medium text-foreground">
                        Name
                    </label>
                    <Input
                        id="loc-name"
                        value={name}
                        onChange={(e) => setName(e.target.value)}
                        placeholder="e.g. Muir tennis courts"
                    />
                    {errors.name && (
                        <p className="text-sm text-destructive-text">{errors.name}</p>
                    )}
                </div>

                <div className="grid grid-cols-2 gap-3">
                    <div className="space-y-1.5">
                        <label htmlFor="loc-lat" className="text-sm font-medium text-foreground">
                            Latitude
                        </label>
                        <Input
                            id="loc-lat"
                            inputMode="decimal"
                            value={latitude}
                            onChange={(e) => setLatitude(e.target.value)}
                            placeholder="32.8801"
                        />
                        {errors.latitude && (
                            <p className="text-sm text-destructive-text">{errors.latitude}</p>
                        )}
                    </div>
                    <div className="space-y-1.5">
                        <label htmlFor="loc-lng" className="text-sm font-medium text-foreground">
                            Longitude
                        </label>
                        <Input
                            id="loc-lng"
                            inputMode="decimal"
                            value={longitude}
                            onChange={(e) => setLongitude(e.target.value)}
                            placeholder="-117.2340"
                        />
                        {errors.longitude && (
                            <p className="text-sm text-destructive-text">{errors.longitude}</p>
                        )}
                    </div>
                </div>

                <div className="grid grid-cols-2 gap-3">
                    <div className="space-y-1.5">
                        <label
                            htmlFor="loc-from-start"
                            className="text-sm font-medium text-foreground"
                        >
                            From destination (min)
                        </label>
                        <Input
                            id="loc-from-start"
                            inputMode="numeric"
                            value={minutesFromStart}
                            onChange={(e) => setMinutesFromStart(e.target.value)}
                            placeholder="—"
                        />
                    </div>
                    <div className="space-y-1.5">
                        <label
                            htmlFor="loc-to-end"
                            className="text-sm font-medium text-foreground"
                        >
                            To destination (min)
                        </label>
                        <Input
                            id="loc-to-end"
                            inputMode="numeric"
                            value={minutesToEnd}
                            onChange={(e) => setMinutesToEnd(e.target.value)}
                            placeholder="—"
                        />
                    </div>
                </div>
                <p className="text-xs text-muted-foreground">
                    Drive time between this stop and the destination (church). Leave blank if
                    routes never start or end here.
                </p>
                {errors.minutes && (
                    <p className="text-sm text-destructive-text">{errors.minutes}</p>
                )}
            </div>

            <DialogFooter>
                <Button variant="outline" onClick={onClose}>
                    Cancel
                </Button>
                <Button onClick={handleSubmit} disabled={submitting}>
                    {submitting ? 'Saving…' : isEdit ? 'Save changes' : 'Create location'}
                </Button>
            </DialogFooter>
        </>
    )
}

export function LocationFormDialog({
    state,
    submitting,
    onSubmit,
    onClose,
}: LocationFormDialogProps) {
    return (
        <Dialog open={state != null} onOpenChange={(open) => { if (!open) onClose() }}>
            <DialogContent className="sm:max-w-md">
                {state && (
                    <LocationFormBody
                        key={state.location?.id ?? 'new'}
                        state={state}
                        submitting={submitting}
                        onSubmit={onSubmit}
                        onClose={onClose}
                    />
                )}
            </DialogContent>
        </Dialog>
    )
}
