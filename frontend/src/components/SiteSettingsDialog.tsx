import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Settings } from 'lucide-react'
import { apiFetch } from '../lib/api'
import type { DayOfWeek, FellowshipSeason, LateReactionWindow, LateReactionWindows } from '../types'
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
} from './ui/dialog'

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
                </div>
            </DialogContent>
        </Dialog>
    )
}

export default SiteSettingsDialog
