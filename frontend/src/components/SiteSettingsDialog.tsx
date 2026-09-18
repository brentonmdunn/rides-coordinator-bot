import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Settings } from 'lucide-react'
import { toast } from 'sonner'
import { apiFetch, ApiError } from '../lib/api'
import type {
    DayOfWeek,
    FellowshipSeason,
    LateReactionWindow,
    LateReactionWindows,
    PickupSummaryEntry,
    PickupSummarySlot,
    PickupSummariesResponse,
} from '../types'
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
} from './ui/dialog'
import { Switch } from './ui/switch'

interface SiteSettingsDialogProps {
    open: boolean
    onOpenChange: (open: boolean) => void
    canManage: boolean
}

const DAYS_OF_WEEK: DayOfWeek[] = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

const LATE_REACTION_ROWS: { key: keyof LateReactionWindows; label: string }[] = [
    { key: 'wednesday', label: 'Wednesday fellowship' },
    { key: 'friday', label: 'Friday fellowship' },
    { key: 'sunday', label: 'Sunday (service + class)' },
]

interface PickupSummaryRowConfig {
    slot: PickupSummarySlot
    label: string
}

const PICKUP_SUMMARY_ROWS: PickupSummaryRowConfig[] = [
    { slot: 'friday', label: 'Friday fellowship pickups' },
    { slot: 'sunday', label: 'Sunday service pickups' },
]

const DAY_ABBREVIATIONS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

/** Pads a number to two digits, e.g. for `<input type="time">` values. */
function pad2(n: number): string {
    return n.toString().padStart(2, '0')
}

/** Converts `hour`/`minute` into the `HH:MM` string `<input type="time">` expects. */
function toTimeInputValue(hour: number, minute: number): string {
    return `${pad2(hour)}:${pad2(minute)}`
}

/** Formats an hour/minute pair as a friendly 12-hour time, e.g. "11:00 AM". */
function formatTime12(hour: number, minute: number): string {
    const period = hour < 12 ? 'AM' : 'PM'
    const hour12 = hour % 12 === 0 ? 12 : hour % 12
    return `${hour12}:${pad2(minute)} ${period}`
}

/** Formats a default schedule as "Fri 11:00 AM". */
function formatDefaultHint(defaultValue: { day_of_week: number; hour: number; minute: number }): string {
    return `${DAY_ABBREVIATIONS[defaultValue.day_of_week]} ${formatTime12(defaultValue.hour, defaultValue.minute)}`
}

function apiErrorMessage(error: unknown, fallback: string): string {
    if (error instanceof ApiError) return error.detail
    if (error instanceof Error) return error.message
    return fallback
}

const selectClassName =
    'min-w-0 flex-1 rounded-md border border-border bg-background text-foreground text-sm px-1.5 py-1 disabled:opacity-50 disabled:cursor-not-allowed'
const timeInputClassName =
    'shrink-0 rounded-md border border-border bg-background text-foreground text-sm px-1.5 py-1 disabled:opacity-50 disabled:cursor-not-allowed'

/** Returns true if `start` is strictly after `end`, given "HH:MM" strings. */
function isTimeAfter(start: string, end: string): boolean {
    return start > end
}

function hasInvertedWindow(windows: LateReactionWindows): boolean {
    return Object.values(windows).some(
        (window) => window.start_day === window.end_day && isTimeAfter(window.start_time, window.end_time),
    )
}

interface PickupSummaryRowProps {
    config: PickupSummaryRowConfig
    entry: PickupSummaryEntry
    canManage: boolean
}

function PickupSummaryRow({ config, entry, canManage }: PickupSummaryRowProps) {
    const queryClient = useQueryClient()
    const allowedDays = entry.allowed_days ?? [entry.day_of_week]

    const invalidate = () => queryClient.invalidateQueries({ queryKey: ['pickupSummaries'] })

    const putMutation = useMutation({
        mutationFn: async (next: { enabled: boolean; day_of_week: number; hour: number; minute: number }) => {
            const response = await apiFetch(`/api/ask-rides/pickup-summaries/${config.slot}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(next),
            })
            return response.json() as Promise<PickupSummaryEntry>
        },
        onSuccess: (data) => {
            invalidate()
            if (data.warning) toast.warning(data.warning)
        },
    })

    const resetMutation = useMutation({
        mutationFn: async () => {
            const response = await apiFetch(`/api/ask-rides/pickup-summaries/${config.slot}`, {
                method: 'DELETE',
            })
            return response.json() as Promise<PickupSummaryEntry>
        },
        onSuccess: (data) => {
            invalidate()
            if (data.warning) toast.warning(data.warning)
        },
    })

    const isPending = putMutation.isPending || resetMutation.isPending
    const disabled = !canManage || isPending

    const handleToggle = (checked: boolean) => {
        putMutation.mutate({
            enabled: checked,
            day_of_week: entry.day_of_week,
            hour: entry.hour,
            minute: entry.minute,
        })
    }

    const handleDayChange = (value: string) => {
        putMutation.mutate({
            enabled: entry.enabled,
            day_of_week: Number(value),
            hour: entry.hour,
            minute: entry.minute,
        })
    }

    // The time input fires onChange per segment while typing, so edits stay in a local
    // draft and only save on blur — otherwise half-typed times would PUT (and 422).
    const serverTime = toTimeInputValue(entry.hour, entry.minute)
    const [timeDraft, setTimeDraft] = useState<string | null>(null)

    const commitTime = () => {
        if (timeDraft === null || timeDraft === serverTime) {
            setTimeDraft(null)
            return
        }
        const [hourStr, minuteStr] = timeDraft.split(':')
        const hour = Number(hourStr)
        const minute = Number(minuteStr)
        if (!hourStr || !minuteStr || Number.isNaN(hour) || Number.isNaN(minute)) {
            setTimeDraft(null)
            return
        }
        putMutation.mutate(
            { enabled: entry.enabled, day_of_week: entry.day_of_week, hour, minute },
            { onSettled: () => setTimeDraft(null) },
        )
    }

    const errorMessage = putMutation.isError
        ? apiErrorMessage(putMutation.error, 'Failed to save — try again')
        : resetMutation.isError
          ? apiErrorMessage(resetMutation.error, 'Failed to reset — try again')
          : null

    return (
        <div>
            <div className="flex items-center justify-between gap-2 mb-1.5">
                <p className="text-xs font-medium text-foreground">{config.label}</p>
                <Switch
                    aria-label={`${config.label} enabled`}
                    checked={entry.enabled}
                    onCheckedChange={handleToggle}
                    disabled={disabled}
                />
            </div>
            <div className="flex w-full flex-wrap items-center gap-1.5">
                <select
                    aria-label="Day"
                    value={entry.day_of_week}
                    onChange={(e) => handleDayChange(e.target.value)}
                    disabled={disabled}
                    className={selectClassName}
                >
                    {allowedDays.map((day) => (
                        <option key={day} value={day}>
                            {DAY_ABBREVIATIONS[day]}
                        </option>
                    ))}
                </select>
                <input
                    aria-label="Time"
                    type="time"
                    value={timeDraft ?? serverTime}
                    onChange={(e) => setTimeDraft(e.target.value)}
                    onBlur={commitTime}
                    disabled={disabled}
                    className={timeInputClassName}
                />
                {entry.is_customized && (
                    <button
                        type="button"
                        onClick={() => resetMutation.mutate()}
                        disabled={disabled}
                        className="px-2 py-1 text-xs font-medium rounded-md border border-border bg-background text-foreground hover:bg-muted disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                        Reset to default
                    </button>
                )}
                {entry.default && (
                    <span className="text-xs text-muted-foreground">
                        Default: {formatDefaultHint(entry.default)}
                    </span>
                )}
            </div>
            {errorMessage && <p className="mt-1 text-xs text-destructive-text">{errorMessage}</p>}
        </div>
    )
}

function SiteSettingsDialog({ open, onOpenChange, canManage }: SiteSettingsDialogProps) {
    const queryClient = useQueryClient()

    const { data: seasonData } = useQuery<{ season: FellowshipSeason }>({
        queryKey: ['fellowshipSeason'],
        queryFn: async () => {
            const response = await apiFetch('/api/ask-rides/fellowship-season')
            return response.json()
        },
        enabled: open,
    })

    const season = seasonData?.season ?? 'friday'

    const seasonMutation = useMutation({
        mutationFn: async (newSeason: FellowshipSeason) => {
            const response = await apiFetch('/api/ask-rides/fellowship-season', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ season: newSeason }),
            })
            return response.json()
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['fellowshipSeason'] })
            queryClient.invalidateQueries({ queryKey: ['askRidesStatus'] })
        },
    })

    const { data: lateReactionWindowsData } = useQuery<LateReactionWindows>({
        queryKey: ['lateReactionWindows'],
        queryFn: async () => {
            const response = await apiFetch('/api/ask-rides/late-reaction-windows')
            return response.json()
        },
        enabled: open,
    })

    const [lateReactionDraft, setLateReactionDraft] = useState<LateReactionWindows | null>(null)
    const [prevLateReactionData, setPrevLateReactionData] = useState<LateReactionWindows | null>(null)
    const [wasOpen, setWasOpen] = useState(open)

    // Adjust draft state during render (per React docs) rather than in a useEffect, so the
    // draft resets to the server value both when fresh data arrives and when the dialog reopens.
    if (open !== wasOpen) {
        setWasOpen(open)
        const nextData = open ? (lateReactionWindowsData ?? null) : null
        setLateReactionDraft(nextData)
        setPrevLateReactionData(nextData)
    } else if (lateReactionWindowsData && lateReactionWindowsData !== prevLateReactionData) {
        setPrevLateReactionData(lateReactionWindowsData)
        setLateReactionDraft(lateReactionWindowsData)
    }

    const lateReactionWindowsMutation = useMutation({
        mutationFn: async (windows: LateReactionWindows) => {
            const response = await apiFetch('/api/ask-rides/late-reaction-windows', {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(windows),
            })
            return response.json()
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['lateReactionWindows'] })
        },
    })

    const updateLateReactionField = (
        key: keyof LateReactionWindows,
        field: keyof LateReactionWindow,
        value: string,
    ) => {
        setLateReactionDraft((prev) => {
            if (!prev) return prev
            return {
                ...prev,
                [key]: {
                    ...prev[key],
                    [field]: value,
                },
            }
        })
    }

    const lateReactionIsDirty =
        !!lateReactionDraft &&
        !!lateReactionWindowsData &&
        JSON.stringify(lateReactionDraft) !== JSON.stringify(lateReactionWindowsData)

    const lateReactionHasInvertedWindow = !!lateReactionDraft && hasInvertedWindow(lateReactionDraft)

    const { data: pickupSummariesData } = useQuery<PickupSummariesResponse>({
        queryKey: ['pickupSummaries'],
        queryFn: async () => {
            const response = await apiFetch('/api/ask-rides/pickup-summaries')
            return response.json()
        },
        enabled: open,
    })

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="sm:max-w-lg">
                <DialogHeader>
                    <DialogTitle className="flex items-center gap-2">
                        <Settings className="h-4 w-4" />
                        Site Settings
                    </DialogTitle>
                </DialogHeader>

                <div className="space-y-4">
                    <div>
                        <p className="text-base font-semibold text-foreground mb-1">Fellowship night</p>
                        <p className="text-xs text-muted-foreground mb-3">
                            Controls which fellowship ride job is active and shown on the dashboard.
                        </p>
                        <div className="inline-flex rounded-md border border-border overflow-hidden">
                            <button
                                onClick={() => seasonMutation.mutate('friday')}
                                disabled={seasonMutation.isPending || !canManage}
                                className={`px-3 py-1.5 text-sm font-medium transition-colors border-r border-border ${
                                    season === 'friday'
                                        ? 'bg-info/15 text-info-text'
                                        : 'bg-background text-muted-foreground hover:bg-muted'
                                } disabled:opacity-50 disabled:cursor-not-allowed`}
                            >
                                🎓 Friday Fellowship
                            </button>
                            <button
                                onClick={() => seasonMutation.mutate('wednesday')}
                                disabled={seasonMutation.isPending || !canManage}
                                className={`px-3 py-1.5 text-sm font-medium transition-colors ${
                                    season === 'wednesday'
                                        ? 'bg-info/15 text-info-text'
                                        : 'bg-background text-muted-foreground hover:bg-muted'
                                } disabled:opacity-50 disabled:cursor-not-allowed`}
                            >
                                ☀️ Wed. Fellowship
                            </button>
                        </div>
                        {seasonMutation.isError && (
                            <p className="mt-2 text-xs text-destructive-text">Failed to switch — try again</p>
                        )}
                        {!canManage && (
                            <p className="mt-2 text-xs text-muted-foreground">Admin access required to change this setting.</p>
                        )}
                    </div>

                    <div>
                        <p className="text-base font-semibold text-foreground mb-1">Late reaction windows</p>
                        <p className="text-xs text-muted-foreground mb-3">
                            When a rides reaction counts as late and gets logged.
                        </p>

                        {lateReactionDraft && (
                            <div className="space-y-3">
                                {LATE_REACTION_ROWS.map(({ key, label }) => {
                                    const window = lateReactionDraft[key]
                                    return (
                                        <div key={key}>
                                            <p className="text-xs font-medium text-foreground mb-1.5">
                                                {label}
                                            </p>
                                            <div className="flex w-full flex-col gap-1.5 sm:flex-row sm:items-center">
                                                <div className="flex w-full min-w-0 items-center gap-1.5 sm:flex-1">
                                                    <select
                                                        value={window.start_day}
                                                        onChange={(e) =>
                                                            updateLateReactionField(key, 'start_day', e.target.value)
                                                        }
                                                        disabled={!canManage || lateReactionWindowsMutation.isPending}
                                                        className={selectClassName}
                                                    >
                                                        {DAYS_OF_WEEK.map((day) => (
                                                            <option key={day} value={day}>
                                                                {day.slice(0, 3)}
                                                            </option>
                                                        ))}
                                                    </select>
                                                    <input
                                                        type="time"
                                                        value={window.start_time}
                                                        onChange={(e) =>
                                                            updateLateReactionField(key, 'start_time', e.target.value)
                                                        }
                                                        disabled={!canManage || lateReactionWindowsMutation.isPending}
                                                        className={timeInputClassName}
                                                    />
                                                </div>
                                                <span className="text-xs text-muted-foreground shrink-0 self-center sm:hidden">
                                                    ↓
                                                </span>
                                                <span className="hidden text-xs text-muted-foreground shrink-0 sm:inline">
                                                    →
                                                </span>
                                                <div className="flex w-full min-w-0 items-center gap-1.5 sm:flex-1">
                                                    <select
                                                        value={window.end_day}
                                                        onChange={(e) =>
                                                            updateLateReactionField(key, 'end_day', e.target.value)
                                                        }
                                                        disabled={!canManage || lateReactionWindowsMutation.isPending}
                                                        className={selectClassName}
                                                    >
                                                        {DAYS_OF_WEEK.map((day) => (
                                                            <option key={day} value={day}>
                                                                {day.slice(0, 3)}
                                                            </option>
                                                        ))}
                                                    </select>
                                                    <input
                                                        type="time"
                                                        value={window.end_time}
                                                        onChange={(e) =>
                                                            updateLateReactionField(key, 'end_time', e.target.value)
                                                        }
                                                        disabled={!canManage || lateReactionWindowsMutation.isPending}
                                                        className={timeInputClassName}
                                                    />
                                                </div>
                                            </div>
                                        </div>
                                    )
                                })}
                            </div>
                        )}

                        {lateReactionHasInvertedWindow && (
                            <p className="mt-2 text-xs text-warning-text">
                                Start time must be before end time when start and end day are the same.
                            </p>
                        )}

                        {lateReactionIsDirty && (
                            <button
                                onClick={() => lateReactionDraft && lateReactionWindowsMutation.mutate(lateReactionDraft)}
                                disabled={
                                    !canManage ||
                                    lateReactionWindowsMutation.isPending ||
                                    lateReactionHasInvertedWindow
                                }
                                className="mt-3 px-3 py-1.5 text-sm font-medium rounded-md border border-border bg-background text-foreground hover:bg-muted disabled:opacity-50 disabled:cursor-not-allowed"
                            >
                                {lateReactionWindowsMutation.isPending ? 'Saving…' : 'Save'}
                            </button>
                        )}

                        {lateReactionWindowsMutation.isError && (
                            <p className="mt-2 text-xs text-destructive-text">Failed to save — try again</p>
                        )}
                        {!canManage && (
                            <p className="mt-2 text-xs text-muted-foreground">
                                Ride coordinator access required to change this setting.
                            </p>
                        )}
                    </div>

                    <div>
                        <p className="text-base font-semibold text-foreground mb-1">Pickup summaries</p>
                        <p className="text-xs text-muted-foreground mb-1">
                            Posts the pickup list to the ride coordinators channel <strong>before</strong> the
                            event — the Friday summary on or before Friday, the Sunday summary on or before
                            Saturday. It only includes people who have reacted by then, and it's skipped if
                            that week's ask-rides message hasn't gone out yet or is paused.
                        </p>
                        <p className="text-xs text-muted-foreground mb-3">
                            Nothing sends unless the <code className="text-xs bg-muted px-1 py-0.5 rounded">friday_pickups_summary_job</code> /{' '}
                            <code className="text-xs bg-muted px-1 py-0.5 rounded">sunday_pickups_summary_job</code> feature flag is also on.
                        </p>

                        {pickupSummariesData && (
                            <div className="space-y-3">
                                {PICKUP_SUMMARY_ROWS.map((config) => (
                                    <PickupSummaryRow
                                        key={config.slot}
                                        config={config}
                                        entry={pickupSummariesData.summaries[config.slot]}
                                        canManage={canManage}
                                    />
                                ))}
                            </div>
                        )}

                        {!canManage && (
                            <p className="mt-2 text-xs text-muted-foreground">
                                Ride coordinator access required to change this setting.
                            </p>
                        )}
                    </div>
                </div>
            </DialogContent>
        </Dialog>
    )
}

export default SiteSettingsDialog
