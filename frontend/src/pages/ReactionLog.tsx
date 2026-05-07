import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { apiFetch, getApiUrl } from '../lib/api'
import { Button } from '../components/ui/button'
import { PageHeader, PageLayout } from '../components/shared'
import { ModeToggle } from '../components/mode-toggle'

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

// ── Helpers ────────────────────────────────────────────────────────────────

function weekToDateRange(week: string): { from: string; to: string } | null {
    // week is "YYYY-Www", e.g. "2026-W19"
    const match = week.match(/^(\d{4})-W(\d{2})$/)
    if (!match) return null
    const year = parseInt(match[1])
    const weekNum = parseInt(match[2])
    // ISO week 1 = week containing first Thursday of the year
    // Monday of week N: Jan 4 + 7*(N-1) days, adjusted to Monday
    const jan4 = new Date(year, 0, 4)
    const monday = new Date(jan4)
    monday.setDate(jan4.getDate() - ((jan4.getDay() + 6) % 7) + (weekNum - 1) * 7)
    const sunday = new Date(monday)
    sunday.setDate(monday.getDate() + 6)
    const fmt = (d: Date) => d.toISOString().slice(0, 10)
    return { from: fmt(monday), to: fmt(sunday) }
}

// ── Constants ──────────────────────────────────────────────────────────────

type RideTypeOption = { value: RideType; label: string }

const RIDE_TYPE_OPTIONS: RideTypeOption[] = [
    { value: 'friday', label: 'Friday' },
    { value: 'sunday', label: 'Sunday' },
    { value: 'sunday_class', label: 'Sunday Class' },
    { value: 'wednesday', label: 'Wednesday' },
]

function currentWeekRange(): { from: string; to: string } {
    const today = new Date()
    const monday = new Date(today)
    monday.setDate(today.getDate() - ((today.getDay() + 6) % 7))
    const sunday = new Date(monday)
    sunday.setDate(monday.getDate() + 6)
    const fmt = (d: Date) => d.toISOString().slice(0, 10)
    return { from: fmt(monday), to: fmt(sunday) }
}

const THIS_WEEK = currentWeekRange()

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
            <span className="inline-flex items-center justify-center w-20 px-2 py-0.5 rounded text-xs font-semibold bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-300">
                Reacted
            </span>
        )
    }
    return (
        <span className="inline-flex items-center justify-center w-20 px-2 py-0.5 rounded text-xs font-semibold bg-slate-100 text-slate-500 dark:bg-zinc-800 dark:text-zinc-400">
            Removed
        </span>
    )
}

function EventRow({ event }: { event: ReactionEvent }) {
    return (
        <div className="flex items-center gap-3 py-2.5 border-b border-border last:border-0">
            <span className="text-xs text-muted-foreground whitespace-nowrap min-w-[160px]">
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
        staleTime: 60_000,
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
                    eyebrow={
                        <Link
                            to="/"
                            className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground mb-4 transition-colors"
                        >
                            <ArrowLeft className="w-3.5 h-3.5" />
                            Back to Dashboard
                        </Link>
                    }
                    title="📜 Reaction Log"
                    description="Chronological log of emoji reactions added or removed from ride messages."
                    actions={<ModeToggle />}
                />
            }
        >
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

                {/* Date range + emoji */}
                <div className="flex flex-wrap gap-4 items-end">
                    <div className="flex flex-col gap-1">
                        <label
                            htmlFor="week-filter"
                            className="text-xs font-semibold text-muted-foreground uppercase tracking-widest"
                        >
                            Week
                        </label>
                        <input
                            id="week-filter"
                            type="week"
                            onChange={(e) => {
                                const range = weekToDateRange(e.target.value)
                                if (range) {
                                    setFilters((prev) => ({
                                        ...prev,
                                        date_from: range.from,
                                        date_to: range.to,
                                    }))
                                }
                            }}
                            className="h-9 px-3 rounded-md border border-input bg-background text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
                        />
                    </div>
                    <div className="flex flex-col gap-1">
                        <label
                            htmlFor="date-from"
                            className="text-xs font-semibold text-muted-foreground uppercase tracking-widest"
                        >
                            From
                        </label>
                        <input
                            id="date-from"
                            type="date"
                            value={filters.date_from}
                            onChange={(e) => setFilter('date_from', e.target.value)}
                            className="h-9 px-3 rounded-md border border-input bg-background text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
                        />
                    </div>
                    <div className="flex flex-col gap-1">
                        <label
                            htmlFor="date-to"
                            className="text-xs font-semibold text-muted-foreground uppercase tracking-widest"
                        >
                            To
                        </label>
                        <input
                            id="date-to"
                            type="date"
                            value={filters.date_to}
                            onChange={(e) => setFilter('date_to', e.target.value)}
                            className="h-9 px-3 rounded-md border border-input bg-background text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
                        />
                    </div>
                    <div className="flex flex-col gap-1">
                        <label
                            htmlFor="emoji-filter"
                            className="text-xs font-semibold text-muted-foreground uppercase tracking-widest"
                        >
                            Emoji
                        </label>
                        <select
                            id="emoji-filter"
                            value={filters.emoji}
                            onChange={(e) => setFilter('emoji', e.target.value)}
                            className="h-9 px-3 rounded-md border border-input bg-background text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
                        >
                            <option value="">All</option>
                            {availableEmojis.map((emoji) => (
                                <option key={emoji} value={emoji}>
                                    {emoji}
                                </option>
                            ))}
                        </select>
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
