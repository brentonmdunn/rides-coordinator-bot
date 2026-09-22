/**
 * PickupInfoFormDialog.tsx
 *
 * Create/edit dialog for a person's pickup info — name, Discord username, and
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
import type { PickupInfoOptions, PickupInfoPerson, PickupInfoPersonInput } from '../../types'
import { isValidPhoneInput } from './phone'

const NONE_VALUE = '__none__'
/** Sentinel select value for a location outside the campus living areas. */
const OTHER_VALUE = '__other__'

export interface PickupInfoFormState {
    /** Existing person when editing; null when creating. */
    person: PickupInfoPerson | null
}

interface PickupInfoFormDialogProps {
    state: PickupInfoFormState | null
    options: PickupInfoOptions | undefined
    submitting: boolean
    error: string | null
    onSubmit: (input: PickupInfoPersonInput) => void
    onClose: () => void
}

interface FieldErrors {
    name?: string
    discord_username?: string
    location?: string
    phone?: string
}

function PickupInfoFormBody({
    state,
    options,
    submitting,
    error,
    onSubmit,
    onClose,
}: {
    state: PickupInfoFormState
    options: PickupInfoOptions | undefined
    submitting: boolean
    error: string | null
    onSubmit: (input: PickupInfoPersonInput) => void
    onClose: () => void
}) {
    const [name, setName] = useState(state.person?.name ?? '')
    const [discordUsername, setDiscordUsername] = useState(
        state.person?.discord_username ?? ''
    )
    const [year, setYear] = useState<string>(state.person?.year ?? NONE_VALUE)
    const [phone, setPhone] = useState(state.person?.phone_display ?? state.person?.phone ?? '')

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
    // Mirror the backend's exception: don't re-validate a phone the user didn't
    // touch, so re-saving a row with a legacy invalid phone doesn't error out.
    const initialPhone = state.person?.phone_display ?? state.person?.phone ?? ''
    const phoneUnchanged = phone.trim() === initialPhone.trim()
    const phoneInvalid = !phoneUnchanged && !isValidPhoneInput(phone)

    const handleSubmit = () => {
        const nextErrors: FieldErrors = {}

        const trimmedName = name.trim()
        if (!trimmedName) nextErrors.name = 'Name is required'

        const trimmedCustomLocation = customLocation.trim()
        if (location === OTHER_VALUE && !trimmedCustomLocation) {
            nextErrors.location = 'Enter where they live, or pick a campus area'
        }

        if (phoneInvalid) {
            nextErrors.phone = 'Enter a valid 10-digit US number, e.g. (858) 555-1234'
        }

        setErrors(nextErrors)
        if (Object.keys(nextErrors).length > 0) return

        let submittedLocation: string | null = null
        if (location === OTHER_VALUE) submittedLocation = trimmedCustomLocation
        else if (location !== NONE_VALUE) submittedLocation = location

        const trimmedPhone = phone.trim()

        onSubmit({
            name: trimmedName,
            discord_username: discordUsername.trim() === '' ? null : discordUsername.trim(),
            year: year === NONE_VALUE ? null : year,
            location: submittedLocation,
            phone: trimmedPhone === '' ? null : trimmedPhone,
        })
    }

    return (
        <>
            <DialogHeader>
                <DialogTitle>{isEdit ? 'Edit person' : 'New person'}</DialogTitle>
                <DialogDescription>
                    {isEdit
                        ? "Update this person's pickup info."
                        : 'Add someone to the pickupInfo.'}
                </DialogDescription>
            </DialogHeader>

            <div className="space-y-4">
                <div className="space-y-1.5">
                    <label htmlFor="pickup-info-name" className="text-sm font-medium text-foreground">
                        Name
                    </label>
                    <Input
                        id="pickup-info-name"
                        value={name}
                        onChange={(e) => setName(e.target.value)}
                        placeholder="e.g. Jane Doe"
                    />
                    {errors.name && <p className="text-sm text-destructive-text">{errors.name}</p>}
                </div>

                <div className="space-y-1.5">
                    <label
                        htmlFor="pickup-info-username"
                        className="text-sm font-medium text-foreground"
                    >
                        Discord username
                    </label>
                    <Input
                        id="pickup-info-username"
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

                <div className="space-y-1.5">
                    <label htmlFor="pickup-info-phone" className="text-sm font-medium text-foreground">
                        Phone number
                    </label>
                    <Input
                        id="pickup-info-phone"
                        value={phone}
                        onChange={(e) => setPhone(e.target.value)}
                        placeholder="e.g. (858) 555-1234"
                    />
                    {errors.phone && (
                        <p className="text-sm text-destructive-text">{errors.phone}</p>
                    )}
                </div>

                {location === OTHER_VALUE && (
                    <div className="space-y-1.5">
                        <label
                            htmlFor="pickup-info-custom-location"
                            className="text-sm font-medium text-foreground"
                        >
                            Off-campus location
                        </label>
                        <Input
                            id="pickup-info-custom-location"
                            value={customLocation}
                            onChange={(e) => setCustomLocation(e.target.value)}
                            placeholder="Apartment name or street address"
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
                <Button onClick={handleSubmit} disabled={submitting || phoneInvalid}>
                    {submitting ? 'Saving…' : isEdit ? 'Save changes' : 'Add person'}
                </Button>
            </DialogFooter>
        </>
    )
}

export function PickupInfoFormDialog({
    state,
    options,
    submitting,
    error,
    onSubmit,
    onClose,
}: PickupInfoFormDialogProps) {
    return (
        <Dialog open={state != null} onOpenChange={(open) => { if (!open) onClose() }}>
            <DialogContent className="sm:max-w-md">
                {state && (
                    <PickupInfoFormBody
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
