import { useState, useEffect } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { apiFetch, getApiUrl } from '../lib/api'
import { Button } from '../components/ui/button'
import { Input } from '../components/ui/input'
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from '../components/ui/select'
import { BackLink, PageHeader, PageLayout } from '../components/shared'
import { ModeToggle } from '../components/mode-toggle'
import { ScrollText } from 'lucide-react'
import { QUERY_STALE_1_MIN } from '../lib/constants'

// ── Types ──────────────────────────────────────────────────────────────────

type RideType = 'friday' | 'sunday' | 'sunday_class' | 'wednesday'
type EventAction = 'add' | 'remove'

interface ReactionEvent {
    id: number
    discord_username: string
    display_name: string | null
    emoji: string
    action: EventAction
    occurred_at: string
}

interface RideReactionLog {
    message_id: string
    ride_type: RideType | null
    ride_date: string | null
    label: string
    events: ReactionEvent[]
}

interface ReactionLogResponse {
    rides: RideReactionLog[]
}

interface Filters {
    ride_type: RideType | ''
    date_from: string
    date_to: string
    emoji: string
}

// ── Constants ──────────────────────────────────────────────────────────────

type RideTypeOption = { value: RideType; label: string }

const RIDE_TYPE_OPTIONS: RideTypeOption[] = [
    { value: 'friday', label: 'Friday' },
    { value: 'sunday', label: 'Sunday' },
    { value: 'sunday_class', label: 'Sunday Class' },
    { value: 'wednesday', label: 'Wednesday' },
]

function weekOffset(offset: number): { from: string; to: string } {
    const today = new Date()
    const monday = new Date(today)
    monday.setDate(today.getDate() - ((today.getDay() + 6) % 7) - offset * 7)
    const sunday = new Date(monday)
    sunday.setDate(monday.getDate() + 6)
    const fmt = (d: Date) => d.toISOString().slice(0, 10)
    return { from: fmt(monday), to: fmt(sunday) }
}

const WEEK_PRESETS = [
    { label: 'This week', ...weekOffset(0) },
    { label: 'Last week', ...weekOffset(1) },
    { label: '2 weeks ago', ...weekOffset(2) },
]

const THIS_WEEK = WEEK_PRESETS[0]

const EMPTY_FILTERS: Filters = {
    ride_type: '',
    date_from: THIS_WEEK.from,
    date_to: THIS_WEEK.to,
    emoji: '',
}

// ── Helpers ────────────────────────────────────────────────────────────────

function formatEventTime(iso: string): string {
    // Stored datetimes have no tz suffix — force UTC so conversion to LA is correct
    const utcIso = iso.endsWith('Z') || iso.includes('+') ? iso : iso + 'Z'
    const date = new Date(utcIso)
    const opts = { timeZone: 'America/Los_Angeles' } as const
    const dayName = date.toLocaleDateString('en-US', { ...opts, weekday: 'short' })
    const monthDay = date.toLocaleDateString('en-US', { ...opts, month: 'short', day: 'numeric' })
    const time = date.toLocaleTimeString('en-US', { ...opts, hour: 'numeric', minute: '2-digit' })
    return `${dayName} ${monthDay} · ${time}`
}

function hasActiveFilters(filters: Filters): boolean {
    return (
        filters.ride_type !== '' ||
        filters.date_from !== '' ||
        filters.date_to !== '' ||
        filters.emoji !== ''
    )
}

function buildQueryString(filters: Filters): string {
    const params = new URLSearchParams()
    if (filters.ride_type) params.set('ride_type', filters.ride_type)
    if (filters.date_from) params.set('date_from', filters.date_from)
    if (filters.date_to) params.set('date_to', filters.date_to)
    if (filters.emoji) params.set('emoji', filters.emoji)
    const qs = params.toString()
    return qs ? `?${qs}` : ''
}

// ── Sub-components ─────────────────────────────────────────────────────────

function ActionBadge({ action }: { action: EventAction }) {
    if (action === 'add') {
        return (
            <span className="inline-flex items-center justify-center w-20 px-2 py-0.5 rounded text-xs font-semibold bg-success/15 text-success-text">
                Reacted
            </span>
        )
    }
    return (
        <span className="inline-flex items-center justify-center w-20 px-2 py-0.5 rounded text-xs font-semibold bg-muted text-muted-foreground">
            Removed
        </span>
    )
}

function EventRow({ event }: { event: ReactionEvent }) {
    return (
        <div className="py-2.5 border-b border-border last:border-0">
            <span className="text-xs text-muted-foreground block mb-1.5 sm:hidden">
                {formatEventTime(event.occurred_at)}
            </span>
            <div className="flex items-center gap-3">
                <span className="text-xs text-muted-foreground whitespace-nowrap min-w-[160px] hidden sm:block">
                    {formatEventTime(event.occurred_at)}
                </span>
                <span className="text-xl leading-none">{event.emoji}</span>
                <ActionBadge action={event.action} />
                <div className="flex flex-col items-start min-w-0">
                    <span className="text-sm text-foreground font-medium truncate">
                        {event.display_name ?? `@${event.discord_username}`}
                    </span>
                    {event.display_name && (
                        <span className="text-xs text-muted-foreground">
                            @{event.discord_username}
                        </span>
                    )}
                </div>
            </div>
        </div>
    )
}

function RideCard({ ride }: { ride: RideReactionLog }) {
    return (
        <div className="bg-card border border-border rounded-lg overflow-hidden">
            {/* Card header */}
            <div className="flex items-center justify-between px-5 py-3 bg-muted/50 border-b border-border">
                <h3 className="font-semibold text-foreground">
                    {ride.ride_type ? ride.ride_type.replace('_', ' ').replace(/\b\w/g, (c) => c.toUpperCase()) : 'Unknown'}
                </h3>
                <span className="text-xs font-medium text-muted-foreground uppercase tracking-widest">
                    {ride.events.length} {ride.events.length === 1 ? 'event' : 'events'}
                </span>
            </div>

            {/* Event timeline */}
            <div className="px-5">
                {ride.events.length === 0 ? (
                    <p className="py-6 text-center text-sm text-muted-foreground italic">
                        No events recorded.
                    </p>
                ) : (
                    ride.events.map((event) => (
                        <EventRow key={event.id} event={event} />
                    ))
                )}
            </div>
        </div>
    )
}

function LoadingSkeleton() {
    return (
        <div className="space-y-4 animate-pulse">
            {[1, 2, 3].map((i) => (
                <div key={i} className="bg-card border border-border rounded-lg overflow-hidden">
                    <div className="flex items-center justify-between px-5 py-3 bg-muted/50 border-b border-border">
                        <div className="h-4 bg-muted rounded w-48" />
                        <div className="h-3 bg-muted rounded w-16" />
                    </div>
                    <div className="px-5 py-2 space-y-3">
                        {[1, 2, 3].map((j) => (
                            <div key={j} className="flex items-center gap-3 py-2">
                                <div className="h-3 bg-muted rounded w-40" />
                                <div className="h-5 bg-muted rounded w-6" />
                                <div className="h-4 bg-muted rounded w-16" />
                                <div className="h-3 bg-muted rounded w-28" />
                            </div>
                        ))}
                    </div>
                </div>
            ))}
        </div>
    )
}

// ── Main page ──────────────────────────────────────────────────────────────

function ReactionLog() {
    const [filters, setFilters] = useState<Filters>(EMPTY_FILTERS)
    const [streamError, setStreamError] = useState(false)

    const { data, isLoading, isError, error } = useQuery<ReactionLogResponse>({
        queryKey: ['reaction-log', filters],
        queryFn: async () => {
            const res = await apiFetch(`/api/reaction-log${buildQueryString(filters)}`)
            return res.json() as Promise<ReactionLogResponse>
        },
    })

    // Fetch unfiltered data to populate emoji dropdown regardless of active filters
    const { data: allData } = useQuery<ReactionLogResponse>({
        queryKey: ['reaction-log-all-emojis'],
        queryFn: async () => {
            const res = await apiFetch('/api/reaction-log')
            return res.json() as Promise<ReactionLogResponse>
        },
        staleTime: QUERY_STALE_1_MIN,
    })

    const availableEmojis = Array.from(
        new Set(allData?.rides.flatMap((r) => r.events.map((e) => e.emoji)) ?? [])
    ).sort()

    const queryClient = useQueryClient()

    useEffect(() => {
        const es = new EventSource(getApiUrl('/api/reaction-log/stream'), { withCredentials: true })
        es.onmessage = () => {
            void queryClient.invalidateQueries({ queryKey: ['reaction-log'] })
            void queryClient.invalidateQueries({ queryKey: ['reaction-log-all-emojis'] })
        }
        es.onerror = () => {
            setStreamError(true)
            es.close()
        }
        return () => es.close()
    }, [queryClient])

    const setFilter = <K extends keyof Filters>(key: K, value: Filters[K]) => {
        setFilters((prev) => ({ ...prev, [key]: value }))
    }

    const clearFilters = () => setFilters(EMPTY_FILTERS)

    return (
        <PageLayout
            spacedBody
            header={
                <PageHeader
                    eyebrow={<BackLink to="/" />}
                    title={<span className="inline-flex items-center gap-2"><ScrollText className="h-6 w-6 shrink-0" />Reaction Log</span>}
                    description="Chronological log of emoji reactions added or removed from ride messages."
                    actions={<ModeToggle />}
                />
            }
        >
            {streamError && (
                <div className="bg-warning/10 border border-warning/30 text-warning-text rounded-lg px-4 py-3 text-sm">
                    Live feed disconnected. Refresh to reconnect.
                </div>
            )}
            {/* Filter bar */}
            <div className="bg-card border border-border rounded-lg p-4 space-y-4">
                {/* Ride type buttons */}
                <div>
                    <p className="text-xs font-semibold text-muted-foreground uppercase tracking-widest mb-2">
                        Ride Type
                    </p>
                    <div className="flex flex-wrap gap-2">
                        <Button
                            variant={filters.ride_type === '' ? 'default' : 'outline'}
                            size="sm"
                            onClick={() => setFilter('ride_type', '')}
                        >
                            All
                        </Button>
                        {RIDE_TYPE_OPTIONS.map((opt) => (
                            <Button
                                key={opt.value}
                                variant={filters.ride_type === opt.value ? 'default' : 'outline'}
                                size="sm"
                                onClick={() => setFilter('ride_type', opt.value)}
                            >
                                {opt.label}
                            </Button>
                        ))}
                    </div>
                </div>

                {/* Week presets */}
                <div>
                    <p className="text-xs font-semibold text-muted-foreground uppercase tracking-widest mb-2">
                        Quick Select
                    </p>
                    <div className="flex flex-wrap gap-2">
                        {WEEK_PRESETS.map((preset) => (
                            <Button
                                key={preset.label}
                                variant={
                                    filters.date_from === preset.from && filters.date_to === preset.to
                                        ? 'default'
                                        : 'outline'
                                }
                                size="sm"
                                onClick={() =>
                                    setFilters((prev) => ({
                                        ...prev,
                                        date_from: preset.from,
                                        date_to: preset.to,
                                    }))
                                }
                            >
                                {preset.label}
                            </Button>
                        ))}
                    </div>
                </div>

                {/* Date range + emoji */}
                <div className="flex flex-wrap gap-4 items-end">
                    <div className="flex flex-col gap-1 min-w-35">
                        <label
                            htmlFor="date-from"
                            className="text-xs font-semibold text-muted-foreground uppercase tracking-widest"
                        >
                            From
                        </label>
                        <Input
                            id="date-from"
                            type="date"
                            value={filters.date_from}
                            onChange={(e) => setFilter('date_from', e.target.value)}
                        />
                    </div>
                    <div className="flex flex-col gap-1 min-w-35">
                        <label
                            htmlFor="date-to"
                            className="text-xs font-semibold text-muted-foreground uppercase tracking-widest"
                        >
                            To
                        </label>
                        <Input
                            id="date-to"
                            type="date"
                            value={filters.date_to}
                            onChange={(e) => setFilter('date_to', e.target.value)}
                        />
                    </div>
                    <div className="flex flex-col gap-1 min-w-30">
                        <label
                            htmlFor="emoji-filter"
                            className="text-xs font-semibold text-muted-foreground uppercase tracking-widest"
                        >
                            Emoji
                        </label>
                        <Select
                            value={filters.emoji || '__all__'}
                            onValueChange={(v) => setFilter('emoji', v === '__all__' ? '' : v)}
                        >
                            <SelectTrigger id="emoji-filter">
                                <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value="__all__">All</SelectItem>
                                {availableEmojis.map((emoji) => (
                                    <SelectItem key={emoji} value={emoji}>
                                        {emoji}
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                    </div>
                    {hasActiveFilters(filters) && (
                        <Button variant="ghost" size="sm" onClick={clearFilters} className="self-end">
                            Clear filters
                        </Button>
                    )}
                </div>
            </div>

            {/* Results */}
            {isLoading && <LoadingSkeleton />}

            {isError && (
                <div className="rounded-lg border border-destructive/30 bg-destructive/10 px-5 py-4 text-sm text-destructive">
                    {error instanceof Error ? error.message : 'Failed to load reaction log.'}
                </div>
            )}

            {!isLoading && !isError && data && (
                <>
                    {data.rides.length === 0 ? (
                        <div className="text-center py-16 text-muted-foreground">
                            <p className="text-lg font-medium mb-1">No reactions found</p>
                            <p className="text-sm">
                                {hasActiveFilters(filters)
                                    ? 'Try adjusting or clearing the filters.'
                                    : 'No reactions recorded yet. Reactions will appear here as they happen.'}
                            </p>
                        </div>
                    ) : (
                        <div className="space-y-4">
                            {data.rides.map((ride) => (
                                <RideCard key={ride.message_id} ride={ride} />
                            ))}
                        </div>
                    )}
                </>
            )}
        </PageLayout>
    )
}

export default ReactionLog
