import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { UserPlus, Sparkles, Church, Trash2, MapPin } from 'lucide-react'
import { apiFetch, ApiError } from '../lib/api'
import { InfoToggleButton, InfoPanel } from './InfoHelp'
import ErrorMessage from './ErrorMessage'
import ConfirmDialog from './ConfirmDialog'
import { Button } from './ui/button'
import { Input } from './ui/input'
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from './ui/select'
import { LabeledField, RefreshIconButton, SectionCard } from './shared'

type Day = 'Friday' | 'Sunday'

interface NonDiscordRide {
    name: string
    day: string
    location: string | null
    emoji: string | null
}

/** Sentinel for the "no reaction tag" dropdown option (Select can't use ""). */
const NO_REACTION = '__none__'

/** Sentinel for the "Custom" location option. */
const CUSTOM_LOCATION = '__custom__'

/** Selectable ride-reaction tags per day. Emojis must match the backend Emoji enum. */
const REACTION_OPTIONS: Record<Day, { emoji: string; label: string }[]> = {
    Sunday: [
        { emoji: '🍔', label: 'Lunch' },
        { emoji: '🏠', label: 'No lunch' },
        { emoji: '✳️', label: 'Something else' },
    ],
    Friday: [{ emoji: '🪨', label: 'Friday Fellowship' }],
}

/**
 * A dashboard widget for managing non-Discord rides — pickups for people who are
 * not in Discord and therefore never react to the ride posts. Coordinators can add,
 * list, and remove these entries per ride day.
 */
function NonDiscordRides() {
    const [day, setDay] = useState<Day>('Friday')
    const [name, setName] = useState('')
    const [locationSelect, setLocationSelect] = useState('')
    const [customLocation, setCustomLocation] = useState('')
    const [reaction, setReaction] = useState(NO_REACTION)

    const location = locationSelect === CUSTOM_LOCATION ? customLocation : locationSelect
    const [showInfo, setShowInfo] = useState(false)
    const [pendingDelete, setPendingDelete] = useState<NonDiscordRide | null>(null)
    const queryClient = useQueryClient()

    const { data: campusLocations = [] } = useQuery<string[]>({
        queryKey: ['campusLocations'],
        queryFn: async () => {
            const response = await apiFetch('/api/non-discord-rides/campus-locations')
            return response.json()
        },
        staleTime: Infinity,
    })

    const {
        data: rides,
        isLoading,
        error,
    } = useQuery<NonDiscordRide[]>({
        queryKey: ['nonDiscordRides', day],
        queryFn: async () => {
            const response = await apiFetch(
                `/api/non-discord-rides?day=${encodeURIComponent(day)}`
            )
            return response.json()
        },
        refetchOnWindowFocus: false,
    })

    const addMutation = useMutation({
        mutationFn: async () => {
            const response = await apiFetch('/api/non-discord-rides', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    name: name.trim(),
                    day,
                    location: location.trim(),
                    emoji: reaction === NO_REACTION ? null : reaction,
                }),
            })
            return response.json()
        },
        onSuccess: () => {
            setName('')
            setLocationSelect('')
            setCustomLocation('')
            setReaction(NO_REACTION)
            queryClient.invalidateQueries({ queryKey: ['nonDiscordRides', day] })
        },
    })

    const removeMutation = useMutation({
        mutationFn: async (ride: NonDiscordRide) => {
            await apiFetch('/api/non-discord-rides', {
                method: 'DELETE',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name: ride.name, day: ride.day }),
            })
        },
        onSuccess: () => {
            setPendingDelete(null)
            queryClient.invalidateQueries({ queryKey: ['nonDiscordRides', day] })
        },
    })

    const handleAdd = (e: React.FormEvent) => {
        e.preventDefault()
        if (!name.trim() || !location.trim()) return
        addMutation.mutate()
    }

    const handleDayChange = (next: Day) => {
        setDay(next)
        // Reaction options differ per day, so reset the selection.
        setReaction(NO_REACTION)
    }

    const addError =
        addMutation.error instanceof ApiError
            ? addMutation.error.detail
            : addMutation.error
              ? 'Failed to add pickup'
              : ''

    return (
        <SectionCard
            icon={<UserPlus className="h-4 w-4" />}
            title="Non-Discord Rides"
            actions={
                <>
                    <RefreshIconButton
                        onClick={() =>
                            queryClient.invalidateQueries({ queryKey: ['nonDiscordRides', day] })
                        }
                    />
                    <InfoToggleButton
                        isOpen={showInfo}
                        onClick={() => setShowInfo(!showInfo)}
                        title="About Non-Discord Rides"
                    />
                </>
            }
        >
            <InfoPanel
                isOpen={showInfo}
                onClose={() => setShowInfo(false)}
                title="About Non-Discord Rides"
            >
                <p className="mb-2">
                    Use this to add pickups for people who aren't in Discord and so never react
                    to the ride posts. These entries show up alongside the regular dropoffs.
                </p>
                <p className="text-sm text-muted-foreground">
                    Entries are scoped to the next occurrence of the selected day and are cleared
                    automatically once that day passes.
                </p>
            </InfoPanel>

            {/* Day selector */}
            <div className="mb-6 grid grid-cols-2 gap-3">
                <button
                    type="button"
                    onClick={() => handleDayChange('Friday')}
                    className={`flex items-center justify-center gap-2 px-4 py-3 rounded-lg border text-sm font-medium transition-all ${
                        day === 'Friday'
                            ? 'bg-info/10 border-info text-foreground ring-1 ring-info'
                            : 'bg-card border-border text-foreground hover:bg-accent hover:text-accent-foreground'
                    }`}
                >
                    <Sparkles className="h-4 w-4" />
                    <span>Friday Fellowship</span>
                </button>
                <button
                    type="button"
                    onClick={() => handleDayChange('Sunday')}
                    className={`flex items-center justify-center gap-2 px-4 py-3 rounded-lg border text-sm font-medium transition-all ${
                        day === 'Sunday'
                            ? 'bg-info/10 border-info text-foreground ring-1 ring-info'
                            : 'bg-card border-border text-foreground hover:bg-accent hover:text-accent-foreground'
                    }`}
                >
                    <Church className="h-4 w-4" />
                    <span>Sunday Service</span>
                </button>
            </div>

            {/* Add form */}
            <form onSubmit={handleAdd} className="space-y-4">
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                    <LabeledField label="Name">
                        <Input
                            value={name}
                            onChange={(e) => setName(e.target.value)}
                            placeholder="e.g. Jane Doe"
                        />
                    </LabeledField>
                    <LabeledField label="Pickup Location">
                        <Select value={locationSelect} onValueChange={setLocationSelect}>
                            <SelectTrigger className="w-full">
                                <SelectValue placeholder="Select location…" />
                            </SelectTrigger>
                            <SelectContent>
                                {campusLocations.map((loc) => (
                                    <SelectItem key={loc} value={loc}>{loc}</SelectItem>
                                ))}
                                <SelectItem value={CUSTOM_LOCATION}>Custom…</SelectItem>
                            </SelectContent>
                        </Select>
                        {locationSelect === CUSTOM_LOCATION && (
                            <Input
                                className="mt-2"
                                value={customLocation}
                                onChange={(e) => setCustomLocation(e.target.value)}
                                placeholder="Enter location"
                            />
                        )}
                    </LabeledField>
                    <LabeledField label="Reaction">
                        <Select value={reaction} onValueChange={setReaction}>
                            <SelectTrigger className="w-full">
                                <SelectValue placeholder="None" />
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value={NO_REACTION}>None</SelectItem>
                                {REACTION_OPTIONS[day].map((opt) => (
                                    <SelectItem key={opt.emoji} value={opt.emoji}>
                                        {opt.emoji} {opt.label}
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                    </LabeledField>
                </div>
                <div className="flex items-center gap-3">
                    <Button
                        type="submit"
                        disabled={addMutation.isPending || !name.trim() || !location.trim()}
                    >
                        <UserPlus className="h-4 w-4" />
                        {addMutation.isPending ? 'Adding…' : 'Add Pickup'}
                    </Button>
                </div>
                {addError && <ErrorMessage message={addError} />}
            </form>

            {/* List */}
            <div className="mt-8">
                <h3 className="text-sm font-semibold text-foreground mb-3">
                    Added pickups for {day}
                </h3>

                {isLoading && (
                    <p className="text-center py-6 text-muted-foreground">Loading…</p>
                )}

                {error && !isLoading && (
                    <ErrorMessage message="Failed to load non-Discord rides" />
                )}

                {rides && !isLoading && !error && (
                    rides.length === 0 ? (
                        <p className="text-sm text-muted-foreground py-4 text-center border border-dashed border-border rounded-lg">
                            No non-Discord pickups added for {day} yet.
                        </p>
                    ) : (
                        <ul className="space-y-2">
                            {rides.map((ride) => (
                                <li
                                    key={`${ride.name}-${ride.day}`}
                                    className="flex items-center justify-between gap-3 px-3 py-2 rounded-md bg-muted"
                                >
                                    <div className="min-w-0">
                                        {ride.emoji && (
                                            <span className="mr-1" aria-hidden>
                                                {ride.emoji}
                                            </span>
                                        )}
                                        <span className="font-medium text-foreground">
                                            {ride.name}
                                        </span>
                                        <span className="ml-2 inline-flex items-center gap-1 text-sm text-muted-foreground">
                                            <MapPin className="h-3.5 w-3.5" />
                                            {ride.location || 'No location'}
                                        </span>
                                    </div>
                                    <Button
                                        variant="ghost"
                                        size="sm"
                                        className="h-8 w-8 p-0 text-destructive-text hover:bg-destructive/10"
                                        onClick={() => setPendingDelete(ride)}
                                        title={`Remove ${ride.name}`}
                                        aria-label={`Remove ${ride.name}`}
                                    >
                                        <Trash2 className="h-4 w-4" />
                                    </Button>
                                </li>
                            ))}
                        </ul>
                    )
                )}
            </div>

            <ConfirmDialog
                isOpen={pendingDelete !== null}
                title="Remove pickup"
                description={
                    pendingDelete
                        ? `Remove the pickup for ${pendingDelete.name} on ${pendingDelete.day}?`
                        : ''
                }
                confirmText={removeMutation.isPending ? 'Removing…' : 'Remove'}
                confirmVariant="destructive"
                onConfirm={() => pendingDelete && removeMutation.mutate(pendingDelete)}
                onCancel={() => setPendingDelete(null)}
            />
        </SectionCard>
    )
}

export default NonDiscordRides
