/**
 * SettingsSection.tsx
 *
 * Location-related settings: the pickup adjustment constant and the
 * living-location → pickup-location mapping.
 */

import { useEffect, useState } from 'react'
import { Settings } from 'lucide-react'
import { Button } from '../ui/button'
import { Input } from '../ui/input'
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from '../ui/select'
import { ConfirmDialog } from '../ConfirmDialog'
import { SectionCard } from '../shared'
import type { LivingLocationMapping, ManagedPickupLocation } from '../../types'

interface SettingsSectionProps {
    pickupAdjustment: number
    livingMappings: LivingLocationMapping[]
    locations: ManagedPickupLocation[]
    savingAdjustment: boolean
    savingMapping: boolean
    onSaveAdjustment: (value: number) => void
    onSetMapping: (livingLocation: string, pickupLocationId: number) => Promise<unknown>
    onAnnounce: (livingLocation: string, pickupLocationId: number) => Promise<unknown>
}

export function SettingsSection({
    pickupAdjustment,
    livingMappings,
    locations,
    savingAdjustment,
    savingMapping,
    onSaveAdjustment,
    onSetMapping,
    onAnnounce,
}: SettingsSectionProps) {
    const [announcement, setAnnouncement] = useState<{
        livingLocation: string
        pickupLocationId: number
        pickupName: string
        mapsUrl: string
    } | null>(null)
    const [sending, setSending] = useState(false)
    const [sendError, setSendError] = useState(false)
    const changeMapping = async (livingLocation: string, pickupLocationId: number) => {
        if (livingMappings.find((m) => m.living_location === livingLocation)?.pickup_location_id === pickupLocationId) return
        try {
            await onSetMapping(livingLocation, pickupLocationId)
            setSendError(false)
            const location = locations.find((loc) => loc.id === pickupLocationId)
            setAnnouncement({
                livingLocation, pickupLocationId,
                pickupName: location?.name ?? '',
                mapsUrl: `https://www.google.com/maps/search/?api=1&query=${location?.latitude},${location?.longitude}`,
            })
        } catch {
            // The mutation reports the save error; only prompt after a successful save.
        }
    }
    const sendAnnouncement = async () => {
        if (!announcement || sending) return
        setSending(true)
        setSendError(false)
        try {
            await onAnnounce(announcement.livingLocation, announcement.pickupLocationId)
            setAnnouncement(null)
        } catch {
            setSendError(true)
        } finally {
            setSending(false)
        }
    }
    const [adjustment, setAdjustment] = useState(String(pickupAdjustment))

    useEffect(() => {
        setAdjustment(String(pickupAdjustment))
    }, [pickupAdjustment])

    const parsed = Number(adjustment.trim())
    const isValid = adjustment.trim() !== '' && Number.isInteger(parsed) && parsed >= 0
    const isDirty = isValid && parsed !== pickupAdjustment

    const activeLocations = locations.filter((loc) => loc.is_active)
    const nameById = new Map(locations.map((loc) => [loc.id, loc.name]))
    const sortedMappings = [...livingMappings].sort((a, b) =>
        a.living_location.localeCompare(b.living_location)
    )

    return (
        <SectionCard icon={<Settings className="h-4 w-4" />} title="Location Settings">
            <div className="space-y-6">
                <div className="space-y-1.5">
                    <label
                        htmlFor="pickup-adjustment"
                        className="text-sm font-medium text-foreground"
                    >
                        Pickup adjustment
                    </label>
                    <div className="flex items-center gap-2">
                        <Input
                            id="pickup-adjustment"
                            inputMode="numeric"
                            value={adjustment}
                            onChange={(e) => setAdjustment(e.target.value)}
                            className="w-24"
                        />
                        <Button
                            size="sm"
                            onClick={() => onSaveAdjustment(parsed)}
                            disabled={!isDirty || savingAdjustment}
                        >
                            {savingAdjustment ? 'Saving…' : 'Save'}
                        </Button>
                    </div>
                    <p className="text-xs text-muted-foreground">
                        Minutes added per stop when computing pickup times — buffer for
                        loading up at each location.
                    </p>
                    {adjustment.trim() !== '' && !isValid && (
                        <p className="text-sm text-destructive-text">
                            Must be a whole number ≥ 0
                        </p>
                    )}
                </div>

                <div className="space-y-1.5">
                    <p className="text-sm font-medium text-foreground">
                        Living location → pickup location
                    </p>
                    <p className="text-xs text-muted-foreground mb-2">
                        Which pickup spot riders from each campus living area are grouped
                        under. A pickup location can't be deleted while a living location
                        still points at it.
                    </p>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-2">
                        {sortedMappings.map((mapping) => {
                            // Keep an inactive-but-mapped location selectable so the
                            // current value still renders; flag it as inactive.
                            const mappedIsActive = activeLocations.some(
                                (loc) => loc.id === mapping.pickup_location_id
                            )
                            return (
                                <div
                                    key={mapping.living_location}
                                    className="flex items-center justify-between gap-3"
                                >
                                    <span className="text-sm text-foreground shrink-0">
                                        {mapping.living_location}
                                    </span>
                                    <Select
                                        value={String(mapping.pickup_location_id)}
                                        onValueChange={(value) =>
                                            void changeMapping(mapping.living_location, Number(value))
                                        }
                                        disabled={savingMapping || announcement != null}
                                    >
                                        <SelectTrigger className="w-52">
                                            <SelectValue placeholder="Select location" />
                                        </SelectTrigger>
                                        <SelectContent>
                                            {activeLocations.map((loc) => (
                                                <SelectItem key={loc.id} value={String(loc.id)}>
                                                    {loc.name}
                                                </SelectItem>
                                            ))}
                                            {!mappedIsActive && (
                                                <SelectItem
                                                    value={String(mapping.pickup_location_id)}
                                                >
                                                    {nameById.get(mapping.pickup_location_id) ??
                                                        `#${mapping.pickup_location_id}`}{' '}
                                                    (inactive)
                                                </SelectItem>
                                            )}
                                        </SelectContent>
                                    </Select>
                                </div>
                            )
                        })}
                    </div>
                </div>
            </div>
            <ConfirmDialog
                isOpen={announcement != null}
                title="Announce this pickup change?"
                description="Your pickup spot has been saved. Do you want to send an announcement to #rides-announcements?"
                confirmText={sending ? 'Sending…' : 'Yes, send announcement'}
                cancelText="No, thanks"
                confirmDisabled={sending}
                onConfirm={() => void sendAnnouncement()}
                onCancel={() => { if (!sending) setAnnouncement(null) }}
            >
                {announcement && (
                    <p className="rounded-lg border bg-muted/40 p-3 text-sm">
                        📍 Pickup location update: Riders living in {announcement.livingLocation} will now be picked up at {announcement.pickupName}. Please head to this spot for future rides.
                        <a href={announcement.mapsUrl} target="_blank" rel="noopener noreferrer" className="mt-2 block text-primary underline">View pickup spot on Google Maps</a>
                    </p>
                )}
                {sendError && <p role="alert" className="text-sm text-destructive-text">Announcement could not be sent. Your pickup change is saved. Try again or close this prompt.</p>}
            </ConfirmDialog>
        </SectionCard>
    )
}
