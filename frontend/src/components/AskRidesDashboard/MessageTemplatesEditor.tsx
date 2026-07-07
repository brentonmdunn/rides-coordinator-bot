import { useEffect, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiFetch, getApiUrl } from '../../lib/api'
import { Button } from '../ui/button'
import { Input } from '../ui/input'
import ConfirmDialog from '../ConfirmDialog'
import ErrorMessage from '../ErrorMessage'
import { ListSkeleton } from '../LoadingSkeleton'
import type {
    AskRidesCoordinator,
    AskRidesMessageTemplate,
    AskRidesMessageType,
    AskRidesMessagesResponse,
    AskRidesScheduleEntry,
    AskRidesScheduleResponse,
    AskRidesScheduleSlot,
    AskRidesScheduleTimeWindow,
    FellowshipSeason,
} from '../../types'

// ── Config ───────────────────────────────────────────────────────────────

interface MessageTypeConfig {
    type: AskRidesMessageType
    label: string
    /** Job name used by the existing `/api/ask-rides/upcoming-dates/{jobName}` endpoint. */
    jobName: string
}

const MESSAGE_TYPE_CONFIG: MessageTypeConfig[] = [
    { type: 'wednesday_fellowship', label: 'Wed. Fellowship', jobName: 'wednesday' },
    { type: 'friday_fellowship', label: 'Friday Fellowship', jobName: 'friday' },
    { type: 'sunday_service', label: 'Sunday Service', jobName: 'sunday' },
    { type: 'sunday_class', label: 'Sunday Class', jobName: 'sunday_class' },
]

// The color key IS the content here (a literal brand color the user picks
// for the Discord embed), not a semantic UI intent — so a small local
// color-key -> CSS color map is the correct escape hatch from the OKLCH
// semantic token rule, scoped entirely to this component.
const COLOR_SWATCH_MAP: Record<string, string> = {
    teal: '#1abc9c',
    green: '#2ecc71',
    blue: '#3498db',
    blurple: '#5865f2',
    pink: '#ff66aa',
    magenta: '#e91e8c',
    orange: '#e67e22',
    yellow: '#f1c40f',
    red: '#e74c3c',
    purple: '#9b59b6',
}

const FALLBACK_SWATCH_COLOR = '#94a3b8'

interface ScheduleSlotConfig {
    slot: AskRidesScheduleSlot
    label: string
    description: string
}

const SCHEDULE_SLOT_CONFIG: ScheduleSlotConfig[] = [
    {
        slot: 'wednesday_reminder',
        label: 'Wed. Fellowship Reminder',
        description: 'When the Wednesday-fellowship reminder ping goes out.',
    },
    {
        slot: 'fri_sun_group',
        label: 'Friday/Sunday Group Send',
        description: 'When the combined Friday/Sunday header + messages go out.',
    },
]

// 0=Monday .. 6=Sunday, matches the backend's `day_of_week` convention.
const DAY_OF_WEEK_LABELS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

const TITLE_MAX_LENGTH = 256
const BODY_MAX_LENGTH = 4096

function swatchColor(colorKey: string): string {
    return COLOR_SWATCH_MAP[colorKey] ?? FALLBACK_SWATCH_COLOR
}

// ── Helpers ──────────────────────────────────────────────────────────────

function formatNextEventDate(isoDate: string): string {
    const date = new Date(isoDate + 'T12:00:00')
    return `${date.getMonth() + 1}/${date.getDate()}`
}

/** Renders a template string with `{date}` substituted and `{ping}` shown as a mention chip. */
function renderPreview(text: string, dateText: string): ReactNode[] {
    const withDate = text.split('{date}').join(dateText)
    const segments = withDate.split('{ping}')
    const nodes: ReactNode[] = []
    segments.forEach((segment, i) => {
        nodes.push(<span key={`t-${i}`}>{segment}</span>)
        if (i < segments.length - 1) {
            nodes.push(
                <span
                    key={`ping-${i}`}
                    className="inline-flex items-center px-1.5 py-0.5 mx-0.5 rounded bg-info/15 text-info-text text-xs font-medium align-middle"
                >
                    @rides coordinator
                </span>,
            )
        }
    })
    return nodes
}

function templatesEqual(a: AskRidesMessageTemplate, b: AskRidesMessageTemplate): boolean {
    return a.title === b.title && a.body === b.body && a.color === b.color
}

/** Pads a number to two digits, e.g. for `<input type="time">` values. */
function pad2(n: number): string {
    return n.toString().padStart(2, '0')
}

/** Converts `day_of_week`/`hour`/`minute` into the `HH:MM` string `<input type="time">` expects. */
function toTimeInputValue(hour: number, minute: number): string {
    return `${pad2(hour)}:${pad2(minute)}`
}

/** Computes the next Date/time (from `now`) matching the given day-of-week (0=Mon..6=Sun) + time. */
function getNextOccurrence(dayOfWeek: number, hour: number, minute: number, now: Date = new Date()): Date {
    const currentDow = (now.getDay() + 6) % 7 // convert JS's 0=Sun..6=Sat to 0=Mon..6=Sun
    let daysUntil = (dayOfWeek - currentDow + 7) % 7
    const candidate = new Date(now.getFullYear(), now.getMonth(), now.getDate(), hour, minute, 0, 0)
    if (daysUntil === 0 && candidate.getTime() <= now.getTime()) {
        daysUntil = 7
    }
    candidate.setDate(candidate.getDate() + daysUntil)
    return candidate
}

/** Same style as `StatusCard`'s `formatDateTime` — kept consistent across the dashboard. */
function formatNextOccurrence(date: Date): string {
    return date.toLocaleString('en-US', {
        weekday: 'short',
        month: 'short',
        day: 'numeric',
        hour: 'numeric',
        minute: '2-digit',
        hour12: true,
    })
}

// ── Message template card ───────────────────────────────────────────────

interface MessageTemplateCardProps {
    config: MessageTypeConfig
    template: AskRidesMessageTemplate
    allowedColors: string[]
}

function MessageTemplateCard({ config, template, allowedColors }: MessageTemplateCardProps) {
    const queryClient = useQueryClient()
    const [title, setTitle] = useState(template.title)
    const [body, setBody] = useState(template.body)
    const [color, setColor] = useState(template.color)
    const [dirty, setDirty] = useState(false)
    const [showResetConfirm, setShowResetConfirm] = useState(false)
    const [remoteConflict, setRemoteConflict] = useState(false)
    const baseline = useRef(template)

    // Sync local edit state from the server value, unless the user has
    // unsaved edits in progress — in that case just flag the conflict so we
    // don't silently clobber what they're typing.
    useEffect(() => {
        if (!dirty) {
            setTitle(template.title)
            setBody(template.body)
            setColor(template.color)
            baseline.current = template
            setRemoteConflict(false)
        } else if (!templatesEqual(template, baseline.current)) {
            setRemoteConflict(true)
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [template])

    const { data: upcomingDates } = useQuery<{ dates: { event_date: string }[] }>({
        queryKey: ['upcomingDates', config.jobName, 0],
        queryFn: async () => {
            const res = await apiFetch(`/api/ask-rides/upcoming-dates/${config.jobName}?count=1&offset=0`)
            return res.json()
        },
    })

    const nextDateText = upcomingDates?.dates[0]
        ? formatNextEventDate(upcomingDates.dates[0].event_date)
        : '{date}'

    const saveMutation = useMutation({
        mutationFn: async () => {
            const res = await apiFetch(`/api/ask-rides/messages/${config.type}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ title, body, color }),
            })
            return res.json() as Promise<AskRidesMessageTemplate>
        },
        onSuccess: () => {
            setDirty(false)
            setRemoteConflict(false)
            void queryClient.invalidateQueries({ queryKey: ['askRidesMessages'] })
        },
    })

    const resetMutation = useMutation({
        mutationFn: async () => {
            const res = await apiFetch(`/api/ask-rides/messages/${config.type}`, {
                method: 'DELETE',
            })
            return res.json() as Promise<AskRidesMessageTemplate>
        },
        onSuccess: () => {
            setDirty(false)
            setRemoteConflict(false)
            setShowResetConfirm(false)
            void queryClient.invalidateQueries({ queryKey: ['askRidesMessages'] })
        },
    })

    const handleTitleChange = (value: string) => {
        setTitle(value)
        setDirty(true)
    }
    const handleBodyChange = (value: string) => {
        setBody(value)
        setDirty(true)
    }
    const handleColorChange = (value: string) => {
        setColor(value)
        setDirty(true)
    }

    const canSave = title.trim().length > 0 && body.trim().length > 0 && !saveMutation.isPending

    return (
        <div className="bg-card rounded-lg border border-border p-5 shadow-sm">
            <div className="flex items-center justify-between gap-2 mb-3">
                <h3 className="text-lg font-semibold text-foreground">{config.label}</h3>
                {template.is_customized && (
                    <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-info/15 text-info-text border border-info/30">
                        Customized
                    </span>
                )}
            </div>

            {remoteConflict && (
                <div className="mb-3 px-3 py-2 rounded-md bg-warning/10 border border-warning/30 text-warning-text text-sm">
                    This message was just updated by someone else — refresh to see it.
                </div>
            )}

            <div className="space-y-3">
                <div>
                    <label htmlFor={`${config.type}-title`} className="block text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-1">
                        Title
                    </label>
                    <Input
                        id={`${config.type}-title`}
                        value={title}
                        maxLength={TITLE_MAX_LENGTH}
                        onChange={(e) => handleTitleChange(e.target.value)}
                    />
                </div>

                <div>
                    <label htmlFor={`${config.type}-body`} className="block text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-1">
                        Body
                    </label>
                    <textarea
                        id={`${config.type}-body`}
                        value={body}
                        maxLength={BODY_MAX_LENGTH}
                        onChange={(e) => handleBodyChange(e.target.value)}
                        rows={4}
                        className="w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm shadow-xs outline-none focus-visible:border-ring focus-visible:ring-ring/50 focus-visible:ring-[3px] resize-y"
                    />
                </div>

                <div>
                    <p className="block text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-1.5">
                        Color
                    </p>
                    <div className="flex flex-wrap gap-2">
                        {allowedColors.map((c) => (
                            <button
                                key={c}
                                type="button"
                                aria-label={`Color ${c}`}
                                aria-pressed={color === c}
                                onClick={() => handleColorChange(c)}
                                style={{ backgroundColor: swatchColor(c) }}
                                className={`w-7 h-7 rounded-full border-2 transition-transform ${
                                    color === c ? 'border-foreground scale-110' : 'border-transparent hover:scale-105'
                                }`}
                            />
                        ))}
                    </div>
                </div>

                {/* Live preview styled like a Discord embed */}
                <div>
                    <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-1.5">
                        Preview
                    </p>
                    <div
                        className="rounded-md bg-muted/50 border border-border pl-3 py-2 pr-3 flex gap-3"
                        style={{ borderLeft: `4px solid ${swatchColor(color)}` }}
                    >
                        <div className="min-w-0">
                            <p className="font-semibold text-foreground break-words">{renderPreview(title, nextDateText)}</p>
                            <p className="text-sm text-muted-foreground whitespace-pre-wrap break-words mt-1">
                                {renderPreview(body, nextDateText)}
                            </p>
                        </div>
                    </div>
                </div>
            </div>

            <div className="flex items-center justify-between gap-2 mt-4 pt-3 border-t border-border">
                <Button
                    type="button"
                    onClick={() => setShowResetConfirm(true)}
                    disabled={resetMutation.isPending}
                    variant="outline"
                    size="sm"
                    className="border-amber-200 text-amber-700 hover:bg-amber-50 hover:text-amber-800 bg-card dark:border-amber-700 dark:text-amber-400 dark:hover:bg-amber-950"
                >
                    ↩ Reset to default
                </Button>
                <Button
                    type="button"
                    onClick={() => saveMutation.mutate()}
                    disabled={!canSave}
                    size="sm"
                >
                    {saveMutation.isPending ? 'Saving...' : 'Save'}
                </Button>
            </div>

            {saveMutation.isError && (
                <div className="mt-3 px-3 py-2 rounded-md bg-destructive/15 border border-destructive/30 text-destructive-text text-sm">
                    ❌ {saveMutation.error instanceof Error ? saveMutation.error.message : 'Failed to save message'}
                </div>
            )}
            {resetMutation.isError && (
                <div className="mt-3 px-3 py-2 rounded-md bg-destructive/15 border border-destructive/30 text-destructive-text text-sm">
                    ❌ {resetMutation.error instanceof Error ? resetMutation.error.message : 'Failed to reset message'}
                </div>
            )}

            <ConfirmDialog
                isOpen={showResetConfirm}
                title={`Reset ${config.label} to default?`}
                description="This discards any customized title, body, and color for this message and restores the original defaults."
                confirmText="Yes, reset"
                confirmVariant="destructive"
                onConfirm={() => resetMutation.mutate()}
                onCancel={() => setShowResetConfirm(false)}
            />
        </div>
    )
}

// ── Ask-rides send schedule ──────────────────────────────────────────────

interface ScheduleSlotRowProps {
    config: ScheduleSlotConfig
    entry: AskRidesScheduleEntry
    allowedDays: number[]
    timeWindow: AskRidesScheduleTimeWindow
    isInactive: boolean
}

function ScheduleSlotRow({ config, entry, allowedDays, timeWindow, isInactive }: ScheduleSlotRowProps) {
    const queryClient = useQueryClient()
    const [dayOfWeek, setDayOfWeek] = useState(entry.day_of_week)
    const [time, setTime] = useState(toTimeInputValue(entry.hour, entry.minute))
    const [dirty, setDirty] = useState(false)
    const [showResetConfirm, setShowResetConfirm] = useState(false)
    const baseline = useRef(entry)

    useEffect(() => {
        if (!dirty) {
            setDayOfWeek(entry.day_of_week)
            setTime(toTimeInputValue(entry.hour, entry.minute))
            baseline.current = entry
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [entry])

    const [hourStr, minuteStr] = time.split(':')
    const hour = Number(hourStr)
    const minute = Number(minuteStr)
    const nextOccurrence = !Number.isNaN(hour) && !Number.isNaN(minute) ? getNextOccurrence(dayOfWeek, hour, minute) : null

    const saveMutation = useMutation({
        mutationFn: async () => {
            const res = await apiFetch(`/api/ask-rides/schedule/${config.slot}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ day_of_week: dayOfWeek, hour, minute }),
            })
            return res.json() as Promise<AskRidesScheduleEntry>
        },
        onSuccess: () => {
            setDirty(false)
            void queryClient.invalidateQueries({ queryKey: ['askRidesSchedule'] })
        },
    })

    const resetMutation = useMutation({
        mutationFn: async () => {
            const res = await apiFetch(`/api/ask-rides/schedule/${config.slot}`, {
                method: 'DELETE',
            })
            return res.json() as Promise<AskRidesScheduleEntry>
        },
        onSuccess: () => {
            setDirty(false)
            setShowResetConfirm(false)
            void queryClient.invalidateQueries({ queryKey: ['askRidesSchedule'] })
        },
    })

    const handleDayChange = (value: string) => {
        setDayOfWeek(Number(value))
        setDirty(true)
    }
    const handleTimeChange = (value: string) => {
        setTime(value)
        setDirty(true)
    }

    const canSave = !Number.isNaN(hour) && !Number.isNaN(minute) && !saveMutation.isPending

    return (
        <div className="rounded-md bg-muted/50 border border-border p-4">
            <div className="flex items-center justify-between gap-2 mb-3">
                <div>
                    <h4 className="font-semibold text-foreground">{config.label}</h4>
                    <p className="text-xs text-muted-foreground">{config.description}</p>
                </div>
                <div className="flex items-center gap-1.5">
                    {isInactive && (
                        <span
                            title="This job is disabled by the current fellowship season setting."
                            className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-muted text-muted-foreground border border-border"
                        >
                            Inactive this season
                        </span>
                    )}
                    {entry.is_customized && (
                        <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-info/15 text-info-text border border-info/30">
                            Customized
                        </span>
                    )}
                </div>
            </div>

            <div className="flex flex-wrap items-end gap-2">
                <div>
                    <label
                        htmlFor={`${config.slot}-day`}
                        className="block text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-1"
                    >
                        Day
                    </label>
                    <select
                        id={`${config.slot}-day`}
                        value={dayOfWeek}
                        onChange={(e) => handleDayChange(e.target.value)}
                        className="h-9 rounded-md border border-input bg-transparent px-3 text-sm shadow-xs outline-none focus-visible:border-ring focus-visible:ring-ring/50 focus-visible:ring-[3px]"
                    >
                        {allowedDays.map((day) => (
                            <option key={day} value={day}>
                                {DAY_OF_WEEK_LABELS[day]}
                            </option>
                        ))}
                    </select>
                </div>

                <div>
                    <label
                        htmlFor={`${config.slot}-time`}
                        className="block text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-1"
                    >
                        Time
                    </label>
                    <Input
                        id={`${config.slot}-time`}
                        type="time"
                        min={toTimeInputValue(timeWindow.min_hour, timeWindow.min_minute)}
                        max={toTimeInputValue(timeWindow.max_hour, timeWindow.max_minute)}
                        value={time}
                        onChange={(e) => handleTimeChange(e.target.value)}
                        className="w-32"
                    />
                </div>

                <Button
                    type="button"
                    onClick={() => setShowResetConfirm(true)}
                    disabled={resetMutation.isPending}
                    variant="outline"
                    size="sm"
                    className="border-amber-200 text-amber-700 hover:bg-amber-50 hover:text-amber-800 bg-card dark:border-amber-700 dark:text-amber-400 dark:hover:bg-amber-950"
                >
                    ↩ Reset to default
                </Button>
                <Button type="button" onClick={() => saveMutation.mutate()} disabled={!canSave} size="sm">
                    {saveMutation.isPending ? 'Saving...' : 'Save'}
                </Button>
            </div>

            {nextOccurrence && (
                <p className="text-sm text-muted-foreground mt-3">
                    Next send: {formatNextOccurrence(nextOccurrence)}
                </p>
            )}

            {saveMutation.isSuccess && saveMutation.data?.warning && (
                <div className="mt-3 px-3 py-2 rounded-md bg-warning/10 border border-warning/30 text-warning-text text-sm">
                    ⚠️ {saveMutation.data.warning}
                </div>
            )}
            {resetMutation.isSuccess && resetMutation.data?.warning && (
                <div className="mt-3 px-3 py-2 rounded-md bg-warning/10 border border-warning/30 text-warning-text text-sm">
                    ⚠️ {resetMutation.data.warning}
                </div>
            )}
            {saveMutation.isError && (
                <div className="mt-3 px-3 py-2 rounded-md bg-destructive/15 border border-destructive/30 text-destructive-text text-sm">
                    ❌ {saveMutation.error instanceof Error ? saveMutation.error.message : 'Failed to save schedule'}
                </div>
            )}
            {resetMutation.isError && (
                <div className="mt-3 px-3 py-2 rounded-md bg-destructive/15 border border-destructive/30 text-destructive-text text-sm">
                    ❌ {resetMutation.error instanceof Error ? resetMutation.error.message : 'Failed to reset schedule'}
                </div>
            )}

            <ConfirmDialog
                isOpen={showResetConfirm}
                title={`Reset ${config.label} to default?`}
                description="This discards the customized send day/time for this schedule and restores the original default."
                confirmText="Yes, reset"
                confirmVariant="destructive"
                onConfirm={() => resetMutation.mutate()}
                onCancel={() => setShowResetConfirm(false)}
            />
        </div>
    )
}

// The `wednesday_reminder` job is fully gated by the fellowship-season feature
// flag, so it goes dormant when Friday season is active. `fri_sun_group` is
// never fully inactive — it also drives the Sunday sends, which aren't gated
// by the season toggle at all — so it never gets this badge.
function isSlotInactive(slot: AskRidesScheduleSlot, season: FellowshipSeason): boolean {
    return slot === 'wednesday_reminder' && season !== 'wednesday'
}

function ScheduleEditor() {
    const { data, isLoading, error } = useQuery<AskRidesScheduleResponse>({
        queryKey: ['askRidesSchedule'],
        queryFn: async () => {
            const res = await apiFetch('/api/ask-rides/schedule')
            return res.json()
        },
    })

    const { data: seasonData } = useQuery<{ season: FellowshipSeason }>({
        queryKey: ['fellowshipSeason'],
        queryFn: async () => {
            const res = await apiFetch('/api/ask-rides/fellowship-season')
            return res.json()
        },
    })
    const season = seasonData?.season ?? 'friday'

    const errorMessage = error instanceof Error ? error.message : ''

    if (isLoading) return null

    return (
        <div className="bg-card rounded-lg border border-border p-5 shadow-sm">
            <h3 className="text-lg font-semibold text-foreground mb-1">Send schedule</h3>
            <p className="text-sm text-muted-foreground mb-3">When the ask-rides messages are sent each week.</p>

            <ErrorMessage message={errorMessage} />

            {data && (
                <div className="space-y-3">
                    {SCHEDULE_SLOT_CONFIG.map((config) => {
                        const entry = data.schedules[config.slot]
                        return (
                            <ScheduleSlotRow
                                key={config.slot}
                                config={config}
                                entry={entry}
                                allowedDays={entry.allowed_days ?? [entry.day_of_week]}
                                timeWindow={data.time_window}
                                isInactive={isSlotInactive(config.slot, season)}
                            />
                        )
                    })}
                </div>
            )}
        </div>
    )
}

// ── Main rides coordinator setting ──────────────────────────────────────

function CoordinatorSettingCard() {
    const queryClient = useQueryClient()
    const [userId, setUserId] = useState('')
    const [dirty, setDirty] = useState(false)

    const { data, isLoading } = useQuery<AskRidesCoordinator>({
        queryKey: ['askRidesCoordinator'],
        queryFn: async () => {
            const res = await apiFetch('/api/ask-rides/coordinator')
            return res.json()
        },
    })

    useEffect(() => {
        if (!dirty && data) {
            setUserId(data.user_id ?? '')
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [data])

    const saveMutation = useMutation({
        mutationFn: async () => {
            const res = await apiFetch('/api/ask-rides/coordinator', {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ user_id: userId }),
            })
            return res.json() as Promise<AskRidesCoordinator>
        },
        onSuccess: () => {
            setDirty(false)
            void queryClient.invalidateQueries({ queryKey: ['askRidesCoordinator'] })
        },
    })

    if (isLoading) return null

    return (
        <div className="bg-card rounded-lg border border-border p-5 shadow-sm">
            <h3 className="text-lg font-semibold text-foreground mb-1">Main rides coordinator</h3>
            <p className="text-sm text-muted-foreground mb-3">
                The Discord user mentioned by <code className="text-xs bg-muted px-1 py-0.5 rounded">{'{ping}'}</code> in the Sunday service message.
            </p>

            {data && !data.configured && (
                <div className="mb-3 px-3 py-2 rounded-md bg-warning/10 border border-warning/30 text-warning-text text-sm">
                    Not configured — the Sunday service message will fall back to "the rides coordinators" until a value is saved.
                </div>
            )}

            <div className="flex flex-wrap items-end gap-2">
                <div className="flex-1 min-w-48">
                    <label htmlFor="coordinator-user-id" className="block text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-1">
                        Discord user ID
                    </label>
                    <Input
                        id="coordinator-user-id"
                        value={userId}
                        onChange={(e) => {
                            setUserId(e.target.value)
                            setDirty(true)
                        }}
                        placeholder="e.g. 123456789012345678"
                        className="font-mono"
                    />
                </div>
                {data?.username && (
                    <span className="inline-flex items-center px-2.5 py-1 rounded-md text-sm font-medium bg-success/15 text-success-text border border-success/30 mb-0.5">
                        {data.display_name ?? `@${data.username}`}
                    </span>
                )}
                <Button
                    type="button"
                    onClick={() => saveMutation.mutate()}
                    disabled={userId.trim().length === 0 || saveMutation.isPending}
                    size="sm"
                >
                    {saveMutation.isPending ? 'Saving...' : 'Save'}
                </Button>
            </div>

            {saveMutation.isSuccess && saveMutation.data?.warning && (
                <div className="mt-3 px-3 py-2 rounded-md bg-warning/10 border border-warning/30 text-warning-text text-sm">
                    ⚠️ {saveMutation.data.warning}
                </div>
            )}
            {saveMutation.isError && (
                <div className="mt-3 px-3 py-2 rounded-md bg-destructive/15 border border-destructive/30 text-destructive-text text-sm">
                    ❌ {saveMutation.error instanceof Error ? saveMutation.error.message : 'Failed to save coordinator'}
                </div>
            )}
        </div>
    )
}

// ── Top-level editor ─────────────────────────────────────────────────────

function MessageTemplatesEditor() {
    const queryClient = useQueryClient()
    const [streamError, setStreamError] = useState(false)

    const { data, isLoading, error } = useQuery<AskRidesMessagesResponse>({
        queryKey: ['askRidesMessages'],
        queryFn: async () => {
            const res = await apiFetch('/api/ask-rides/messages')
            return res.json()
        },
    })

    useEffect(() => {
        const es = new EventSource(getApiUrl('/api/ask-rides/messages/stream'), { withCredentials: true })
        es.onmessage = () => {
            void queryClient.invalidateQueries({ queryKey: ['askRidesMessages'] })
            void queryClient.invalidateQueries({ queryKey: ['askRidesCoordinator'] })
            void queryClient.invalidateQueries({ queryKey: ['askRidesSchedule'] })
        }
        es.onerror = () => {
            setStreamError(true)
            es.close()
        }
        return () => es.close()
    }, [queryClient])

    const errorMessage = error instanceof Error ? error.message : ''

    return (
        <div className="space-y-6">
            {streamError && (
                <div className="px-3 py-2 rounded-md bg-warning/10 border border-warning/30 text-warning-text text-sm">
                    Live updates disconnected. Refresh to see the latest changes.
                </div>
            )}

            <ErrorMessage message={errorMessage} />

            {isLoading && <ListSkeleton rows={4} />}

            {!isLoading && !errorMessage && data && (
                <>
                    <CoordinatorSettingCard />

                    <ScheduleEditor />

                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                        {MESSAGE_TYPE_CONFIG.map((config) => (
                            <MessageTemplateCard
                                key={config.type}
                                config={config}
                                template={data.templates[config.type]}
                                allowedColors={data.allowed_colors}
                            />
                        ))}
                    </div>
                </>
            )}
        </div>
    )
}

export default MessageTemplatesEditor
