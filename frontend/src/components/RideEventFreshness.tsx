import { useEffect, useState } from 'react'
import type { RideFreshness } from '../types'

export default function RideEventFreshness({ freshness }: { freshness?: RideFreshness | null }) {
    const [now, setNow] = useState(() => Date.now())
    useEffect(() => {
        const timer = setInterval(() => setNow(Date.now()), 30_000)
        return () => clearInterval(timer)
    }, [])
    if (!freshness) return null
    const timestamp = freshness.last_reconciled_at ? Date.parse(freshness.last_reconciled_at) : null
    const stale = freshness.is_stale || (timestamp !== null && now - timestamp > 15 * 60_000)
    const label = timestamp !== null
        ? `Last synced ${new Date(timestamp).toLocaleString()}`
        : freshness.source_count > 0 ? 'Waiting for a complete sync' : 'No active Discord source'
    return (
        <div role="status" className={`my-3 rounded-md border px-3 py-2 text-sm ${stale ? 'border-warning/30 bg-warning/10 text-warning-text' : 'border-border text-muted-foreground'}`}>
            {stale && <span className="font-medium">Ride data may be out of date. </span>}
            {label}
            {freshness.errors.length > 0 && <span className="block">{Array.from(new Set(freshness.errors)).join(' · ')}</span>}
        </div>
    )
}
