/**
 * routeBuilderFormat.ts
 *
 * Small formatting helpers for OSRM trip metadata so widget, panel, and
 * sortable list rows render identical chips/labels.
 */

/** Format an OSRM duration (seconds) as a short, human-readable label. */
export function formatDuration(seconds: number | null | undefined): string | null {
    if (seconds == null || !isFinite(seconds) || seconds < 0) return null
    const totalMinutes = Math.max(1, Math.round(seconds / 60))
    if (totalMinutes < 60) return `${totalMinutes} min`
    const hours = Math.floor(totalMinutes / 60)
    const minutes = totalMinutes % 60
    return minutes === 0 ? `${hours} hr` : `${hours} hr ${minutes} min`
}

/** Format an OSRM distance (meters) as a short label in miles. */
export function formatDistanceMiles(meters: number | null | undefined): string | null {
    if (meters == null || !isFinite(meters) || meters < 0) return null
    const miles = meters / 1609.344
    if (miles < 0.1) return '<0.1 mi'
    return `${miles.toFixed(1)} mi`
}

/** Combine total duration + distance into a single chip label. */
export function formatTripSummary(
    totalDuration: number | null,
    totalDistance: number | null
): string | null {
    const dur = formatDuration(totalDuration)
    const dist = formatDistanceMiles(totalDistance)
    if (!dur && !dist) return null
    if (dur && dist) return `${dur} · ${dist}`
    return dur ?? dist
}
