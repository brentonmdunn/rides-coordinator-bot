import { useState } from 'react'
import type { FormEvent } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiFetch } from '../lib/api'
import type { AccountRole, RideFreshness } from '../types'
import { BackLink, PageHeader, PageLayout, SectionCard } from '../components/shared'
import { Button } from '../components/ui/button'
import { Input } from '../components/ui/input'
import ErrorMessage from '../components/ErrorMessage'
import RideEventFreshness from '../components/RideEventFreshness'

interface EventSummary { id: number; message_type: string; event_date: string }
interface Participant { id: number; name: string; location: string | null; details: string | null; source: string; pickup: boolean; return_preference: string; needs_review: boolean }
interface Offer { id: number; discord_user_id: string; discord_username: string; capacity: number | null; availability: string; directions: string[]; return_preference: string }
interface Assignment { request_id: number; driver_offer_id: number; direction: 'pickup' | 'return' }
interface EventDetail extends EventSummary { requests: Participant[]; driver_offers: Offer[]; assignments: Assignment[]; freshness: RideFreshness }

async function write(endpoint: string, method: string, body?: unknown) {
    const response = await apiFetch(endpoint, { method, headers: { 'Content-Type': 'application/json' }, body: body === undefined ? undefined : JSON.stringify(body) })
    return response.json()
}

function EventEditor({ event }: { event: EventDetail }) {
    const queryClient = useQueryClient()
    const [draft, setDraft] = useState<Assignment[] | null>(null)
    const plan = draft ?? event.assignments
    const base = `/api/ride-events/${event.id}`
    const mutation = useMutation({
        mutationFn: ({ path, method, body }: { path: string; method: string; body?: unknown }) => write(`${base}${path}`, method, body),
        onSuccess: (_data, variables) => {
            if (variables.path === '/assignments') setDraft(null)
            queryClient.invalidateQueries({ queryKey: ['rideEvent', event.id] })
            queryClient.invalidateQueries({ queryKey: ['pickupCoverage'] })
            queryClient.invalidateQueries({ queryKey: ['rideCoverage'] })
        },
    })
    const changeAssignment = (request: number, direction: 'pickup' | 'return', value: string) => {
        const next = plan.filter(row => !(row.request_id === request && row.direction === direction))
        if (value) next.push({ request_id: request, direction, driver_offer_id: Number(value) })
        setDraft(next)
    }
    const addRequest = (e: FormEvent<HTMLFormElement>) => {
        e.preventDefault()
        const form = e.currentTarget
        const fields = new FormData(form)
        mutation.mutate({ path: '/requests', method: 'POST', body: { name: fields.get('name'), location: fields.get('location') || null, details: fields.get('details') || null, return_preference: fields.get('return_preference') } }, { onSuccess: () => form.reset() })
    }
    const saveDriver = (e: FormEvent<HTMLFormElement>, offer?: Offer) => {
        e.preventDefault()
        const fields = new FormData(e.currentTarget)
        const userId = offer?.discord_user_id ?? String(fields.get('user_id'))
        mutation.mutate({ path: `/driver-offers/${userId}`, method: 'PUT', body: { discord_username: offer?.discord_username ?? fields.get('username'), capacity: Number(fields.get('capacity')), directions: fields.getAll('directions'), availability: offer?.availability ?? 'available', return_preference: fields.get('return_preference') } })
    }
    return <div className="space-y-6">
        <RideEventFreshness freshness={event.freshness} />
        <div className="flex flex-wrap gap-2">
            <Button variant="outline" disabled={mutation.isPending} onClick={() => mutation.mutate({ path: '/reconcile', method: 'POST' })}>Sync reactions now</Button>
            <Button disabled={mutation.isPending || draft === null} onClick={() => mutation.mutate({ path: '/assignments', method: 'PUT', body: { assignments: plan } })}>Save assignments</Button>
            {draft !== null && <Button variant="ghost" onClick={() => setDraft(null)}>Discard edits</Button>}
        </div>
        <ErrorMessage message={mutation.error instanceof Error ? mutation.error.message : ''} />
        <SectionCard title="Riders and assignments">
            <p className="mb-4 text-sm text-muted-foreground">Confirm driver seats below, then assign each requested leg. Grouping suggestions become confirmed only when assignments are saved here.</p>
            {event.requests.length === 0 && <p className="text-muted-foreground">No active requests recorded.</p>}
            <div className="space-y-3">
                {event.requests.map(request => <div key={request.id} className="rounded-md border border-border p-3 space-y-2">
                    <div className="font-medium">{request.name} <span className="text-sm font-normal text-muted-foreground">· {request.location ?? 'Pickup location needed'} · {request.source}</span></div>
                    {request.needs_review && <p className="text-sm text-warning-text">Needs coordinator review · {request.return_preference} return</p>}
                    {request.details && <p className="whitespace-pre-wrap text-sm">{request.details}</p>}
                    <div className="flex flex-wrap gap-3">
                        {(['pickup', 'return'] as const).filter(direction => direction === 'pickup' ? request.pickup : request.return_preference !== 'none').map(direction => <label key={direction} className="text-sm">
                            {direction === 'pickup' ? 'Pickup' : 'Return'} driver
                            <select disabled={mutation.isPending} className="ml-2 rounded border border-border bg-background p-2" aria-label={`${request.name} ${direction} driver`} value={plan.find(row => row.request_id === request.id && row.direction === direction)?.driver_offer_id ?? ''} onChange={e => changeAssignment(request.id, direction, e.target.value)}>
                                <option value="">Unassigned</option>
                                {event.driver_offers.filter(offer => offer.availability === 'available' && offer.capacity !== null && offer.directions.includes(direction)).map(offer => <option key={offer.id} value={offer.id}>{offer.discord_username} ({offer.capacity} seats)</option>)}
                            </select>
                        </label>)}
                    </div>
                </div>)}
            </div>
        </SectionCard>
        <SectionCard title="Driver offers">
            <p className="mb-4 text-sm text-muted-foreground">Reaction availability does not specify seats. Confirm passenger capacity before assigning riders.</p>
            {event.driver_offers.map(offer => <form key={`${offer.id}:${offer.capacity}:${offer.availability}:${offer.directions.join(',')}`} onSubmit={e => saveDriver(e, offer)} className="mb-3 flex flex-wrap items-center gap-3 rounded-md border border-border p-3">
                <span>{offer.discord_username} · {offer.availability}</span>
                <label className="text-sm">Passenger seats <Input className="w-24" aria-label={`${offer.discord_username} passenger seats`} name="capacity" type="number" required min="1" max="20" defaultValue={offer.capacity ?? ''} /></label>
                {(['pickup', 'return'] as const).map(direction => <label key={direction} className="text-sm"><input type="checkbox" name="directions" value={direction} defaultChecked={offer.directions.includes(direction)} /> {direction}</label>)}
                <label className="text-sm">Return plan <select className="ml-2 rounded border border-border bg-background p-2" name="return_preference" defaultValue={offer.return_preference ?? 'either'}><option value="either">Home or lunch</option><option value="home">Home</option><option value="lunch">Lunch</option><option value="unknown">Unconfirmed</option><option value="custom">Custom</option></select></label>
                <Button variant="outline" size="sm" disabled={mutation.isPending}>Confirm seats</Button>
            </form>)}
            <form onSubmit={e => saveDriver(e)} className="grid gap-3 sm:grid-cols-3">
                <Input name="user_id" aria-label="Driver Discord user ID" placeholder="Discord user ID" pattern="[0-9]+" required />
                <Input name="username" aria-label="Driver username" placeholder="Driver username" required />
                <Input name="capacity" aria-label="New driver passenger seats" placeholder="Passenger seats" type="number" min="1" max="20" required />
                <div className="flex gap-3 text-sm"><label><input name="directions" value="pickup" type="checkbox" defaultChecked /> Pickup</label><label><input name="directions" value="return" type="checkbox" defaultChecked /> Return</label></div>
                <label className="text-sm">Return plan <select className="ml-2 rounded border border-border bg-background p-2" name="return_preference" defaultValue="either"><option value="either">Home or lunch</option><option value="home">Home</option><option value="lunch">Lunch</option><option value="unknown">Unconfirmed</option><option value="custom">Custom</option></select></label>
                <Button variant="outline" disabled={mutation.isPending}>Add driver offer</Button>
            </form>
        </SectionCard>
        <SectionCard title="Add a rider">
            <form onSubmit={addRequest} className="grid gap-3 sm:grid-cols-2">
                <Input name="name" aria-label="Rider name" placeholder="Rider name" required maxLength={100} />
                <Input name="location" aria-label="Rider pickup location" placeholder="Pickup location" maxLength={300} />
                <Input name="details" aria-label="Ride request details" placeholder="Special requirements (optional)" maxLength={4000} />
                <label className="text-sm">Return preference <select className="ml-2 rounded border border-border bg-background p-2" name="return_preference" defaultValue="unknown"><option value="unknown">Unknown</option><option value="home">Home</option><option value="lunch">Lunch</option><option value="custom">Custom</option><option value="none">No return ride</option></select></label>
                <Button disabled={mutation.isPending}>Add request</Button>
            </form>
        </SectionCard>
    </div>
}

export default function RideEvents() {
    const [selectedId, setSelectedId] = useState<number | null>(() => {
        const value = Number(new URLSearchParams(window.location.search).get('event'))
        return Number.isInteger(value) && value > 0 ? value : null
    })
    const { data: me } = useQuery<{ role: AccountRole }>({ queryKey: ['me'], queryFn: async () => (await apiFetch('/api/me')).json() })
    const canManage = me?.role === 'admin' || me?.role === 'ride_coordinator'
    const { data: events, error: listError } = useQuery<EventSummary[]>({
        queryKey: ['rideEvents'], enabled: canManage, refetchInterval: 60_000,
        queryFn: async () => {
            const start = new Date(Date.now() - 7 * 86400_000).toISOString().slice(0, 10)
            const end = new Date(Date.now() + 14 * 86400_000).toISOString().slice(0, 10)
            return (await apiFetch(`/api/ride-events?date_from=${start}&date_to=${end}`)).json()
        },
    })
    const today = new Date().toISOString().slice(0, 10)
    const eventId = selectedId ?? events?.find(event => event.event_date >= today)?.id ?? events?.at(-1)?.id
    const { data, error, isLoading } = useQuery<EventDetail>({ queryKey: ['rideEvent', eventId], enabled: canManage && eventId !== undefined, refetchInterval: 60_000, queryFn: async () => (await apiFetch(`/api/ride-events/${eventId}`)).json() })
    const failure = error ?? listError
    return <PageLayout spacedBody header={<PageHeader eyebrow={<BackLink to="/" />} title="Ride Events" description="Requests, driver seats, and confirmed assignments for each ride." />}>
        {!canManage ? <p className="text-muted-foreground">Ride coordinator access is required.</p> : <>
            <label className="block text-sm">Event <select className="ml-2 rounded border border-border bg-background p-2" aria-label="Ride event" value={eventId ?? ''} onChange={e => setSelectedId(Number(e.target.value))}>
                {!events?.length && <option value="">No events recorded yet</option>}
                {events?.map(event => <option key={event.id} value={event.id}>{event.event_date} · {event.message_type.replaceAll('_', ' ')}</option>)}
            </select></label>
            <ErrorMessage message={failure instanceof Error ? failure.message : ''} />
            {isLoading && <p className="text-muted-foreground">Loading event…</p>}
            {data && <EventEditor key={data.id} event={data} />}
        </>}
    </PageLayout>
}
