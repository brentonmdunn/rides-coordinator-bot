/**
 * RosterFormDialog.tsx
 *
 * Create/edit dialog for a roster person — name, Discord username, and
 * year/location selects. The form body is keyed on the dialog state so
 * fields initialize from props on every open (no state-syncing effects).
 * Server-side validation/conflict errors (400/409) are shown inline.
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
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from '../ui/select'
import type { RosterOptions, RosterPerson, RosterPersonInput } from '../../types'

const NONE_VALUE = '__none__'
/** Sentinel select value for a location outside the campus living areas. */
const OTHER_VALUE = '__other__'

export interface RosterFormState {
    /** Existing person when editing; null when creating. */
    person: RosterPerson | null
}

interface RosterFormDialogProps {
    state: RosterFormState | null
    options: RosterOptions | undefined
    submitting: boolean
    error: string | null
    onSubmit: (input: RosterPersonInput) => void
    onClose: () => void
}

interface FieldErrors {
    name?: string
    discord_username?: string
    location?: string
}

function RosterFormBody({
    state,
    options,
    submitting,
    error,
    onSubmit,
    onClose,
}: {
    state: RosterFormState
    options: RosterOptions | undefined
    submitting: boolean
    error: string | null
    onSubmit: (input: RosterPersonInput) => void
    onClose: () => void
}) {
    const [name, setName] = useState(state.person?.name ?? '')
    const [discordUsername, setDiscordUsername] = useState(
        state.person?.discord_username ?? ''
    )
    const [year, setYear] = useState<string>(state.person?.year ?? NONE_VALUE)

    // An existing location that isn't a campus area (off-campus, or legacy sheet
    // data) opens as "Other" with the value in the free-text field.
    const existingLocation = state.person?.location ?? null
    const startsAsOther =
        existingLocation != null &&
        (options?.locations?.length ?? 0) > 0 &&
        !options!.locations.includes(existingLocation)

    const [location, setLocation] = useState<string>(
        startsAsOther ? OTHER_VALUE : (existingLocation ?? NONE_VALUE)
    )
    const [customLocation, setCustomLocation] = useState(startsAsOther ? existingLocation : '')
    const [errors, setErrors] = useState<FieldErrors>({})

    const isEdit = state.person != null

    const handleSubmit = () => {
        const nextErrors: FieldErrors = {}

        const trimmedName = name.trim()
        if (!trimmedName) nextErrors.name = 'Name is required'

        const trimmedCustomLocation = customLocation.trim()
        if (location === OTHER_VALUE && !trimmedCustomLocation) {
            nextErrors.location = 'Enter where they live, or pick a campus area'
        }

        setErrors(nextErrors)
        if (Object.keys(nextErrors).length > 0) return

        let submittedLocation: string | null = null
        if (location === OTHER_VALUE) submittedLocation = trimmedCustomLocation
        else if (location !== NONE_VALUE) submittedLocation = location

        onSubmit({
            name: trimmedName,
            discord_username: discordUsername.trim() === '' ? null : discordUsername.trim(),
            year: year === NONE_VALUE ? null : year,
            location: submittedLocation,
        })
    }

    return (
        <>
            <DialogHeader>
                <DialogTitle>{isEdit ? 'Edit person' : 'New person'}</DialogTitle>
                <DialogDescription>
                    {isEdit
                        ? "Update this person's roster details."
                        : 'Add someone to the roster.'}
                </DialogDescription>
            </DialogHeader>

            <div className="space-y-4">
                <div className="space-y-1.5">
                    <label htmlFor="roster-name" className="text-sm font-medium text-foreground">
                        Name
                    </label>
                    <Input
                        id="roster-name"
                        value={name}
                        onChange={(e) => setName(e.target.value)}
                        placeholder="e.g. Jane Doe"
                    />
                    {errors.name && <p className="text-sm text-destructive-text">{errors.name}</p>}
                </div>

                <div className="space-y-1.5">
                    <label
                        htmlFor="roster-username"
                        className="text-sm font-medium text-foreground"
                    >
                        Discord username
                    </label>
                    <Input
                        id="roster-username"
                        value={discordUsername}
                        onChange={(e) => setDiscordUsername(e.target.value)}
                        placeholder="e.g. janedoe (optional)"
                    />
                </div>

                <div className="grid grid-cols-2 gap-3">
                    <div className="space-y-1.5">
                        <label className="text-sm font-medium text-foreground">Year</label>
                        <Select value={year} onValueChange={setYear}>
                            <SelectTrigger className="w-full">
                                <SelectValue placeholder="None" />
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value={NONE_VALUE}>None</SelectItem>
                                {(options?.years ?? []).map((value) => (
                                    <SelectItem key={value} value={value}>
                                        {value}
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                    </div>
                    <div className="space-y-1.5">
                        <label className="text-sm font-medium text-foreground">Location</label>
                        <Select value={location} onValueChange={setLocation}>
                            <SelectTrigger className="w-full">
                                <SelectValue placeholder="None" />
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value={NONE_VALUE}>None</SelectItem>
                                {(options?.locations ?? []).map((value) => (
                                    <SelectItem key={value} value={value}>
                                        {value}
                                    </SelectItem>
                                ))}
                                <SelectItem value={OTHER_VALUE}>Other (off campus)</SelectItem>
                            </SelectContent>
                        </Select>
                    </div>
                </div>

                {location === OTHER_VALUE && (
                    <div className="space-y-1.5">
                        <label
                            htmlFor="roster-custom-location"
                            className="text-sm font-medium text-foreground"
                        >
                            Off-campus location
                        </label>
                        <Input
                            id="roster-custom-location"
                            value={customLocation}
                            onChange={(e) => setCustomLocation(e.target.value)}
                            placeholder="e.g. Costa Verde, or a street address"
                        />
                        {errors.location && (
                            <p className="text-sm text-destructive-text">{errors.location}</p>
                        )}
                    </div>
                )}

                {error && <p className="text-sm text-destructive-text">{error}</p>}
            </div>

            <DialogFooter>
                <Button variant="outline" onClick={onClose}>
                    Cancel
                </Button>
                <Button onClick={handleSubmit} disabled={submitting}>
                    {submitting ? 'Saving…' : isEdit ? 'Save changes' : 'Add person'}
                </Button>
            </DialogFooter>
        </>
    )
}

export function RosterFormDialog({
    state,
    options,
    submitting,
    error,
    onSubmit,
    onClose,
}: RosterFormDialogProps) {
    return (
        <Dialog open={state != null} onOpenChange={(open) => { if (!open) onClose() }}>
            <DialogContent className="sm:max-w-md">
                {state && (
                    <RosterFormBody
                        key={state.person?.id ?? 'new'}
                        state={state}
                        options={options}
                        submitting={submitting}
                        error={error}
                        onSubmit={onSubmit}
                        onClose={onClose}
                    />
                )}
            </DialogContent>
        </Dialog>
    )
}
