import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '../lib/api'
import type { RideCoverage } from '../types'
import { AlertTriangle } from 'lucide-react'
import { isFridayWarningWindow, isSundayWarningWindow } from '../lib/utils'
import { QUERY_STALE_5_MIN } from '../lib/constants'

function RideCoverageWarning() {
    // Check Friday ride coverage
    const { data: fridayData } = useQuery<RideCoverage>({
        queryKey: ['rideCoverage', 'friday'],
        queryFn: async () => {
            const response = await apiFetch('/api/check-pickups/friday')
            return response.json()
        },
        staleTime: QUERY_STALE_5_MIN,
        refetchOnWindowFocus: false,
        refetchOnMount: false,
        refetchOnReconnect: false,
    })

    // Check Sunday ride coverage
    const { data: sundayData } = useQuery<RideCoverage>({
        queryKey: ['rideCoverage', 'sunday'],
        queryFn: async () => {
            const response = await apiFetch('/api/check-pickups/sunday')
            return response.json()
        },
        staleTime: QUERY_STALE_5_MIN,
        refetchOnWindowFocus: false,
        refetchOnMount: false,
        refetchOnReconnect: false,
    })

    const fridayNeedsDrivers = fridayData?.message_found && !fridayData?.has_coverage_entries
    const sundayNeedsDrivers = sundayData?.message_found && !sundayData?.has_coverage_entries

    const shouldShowFridayWarning = fridayNeedsDrivers && isFridayWarningWindow()
    const shouldShowSundayWarning = sundayNeedsDrivers && isSundayWarningWindow()

    // Don't show anything if no warnings needed
    if (!shouldShowFridayWarning && !shouldShowSundayWarning) {
        return null
    }

    // Determine warning message
    let message = ''
    if (shouldShowFridayWarning && shouldShowSundayWarning) {
        message = 'Ride requests have been sent for Friday Fellowship and Sunday Service, but no drivers have posted groupings yet.'
    } else if (shouldShowFridayWarning) {
        message = 'The request for rides has been sent for Friday Fellowship, but no drivers have posted groupings yet.'
    } else if (shouldShowSundayWarning) {
        message = 'The request for rides has been sent for Sunday Service, but no drivers have posted groupings yet.'
    }

    return (
        <div className="relative overflow-hidden rounded-xl border border-warning/40 bg-warning/10">
            {/* Gradient accent strip */}
            <div className="h-1 bg-gradient-to-r from-warning via-warning/60 to-transparent" />
            <div className="flex items-start gap-4 px-5 py-4">
                <div className="flex items-center gap-2 shrink-0 mt-0.5">
                    {/* Pulsing dot */}
                    <span className="relative flex h-3 w-3">
                        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-warning opacity-75" />
                        <span className="relative inline-flex rounded-full h-3 w-3 bg-warning" />
                    </span>
                    <AlertTriangle className="h-5 w-5 text-warning-text" />
                </div>
                <div className="flex-1 min-w-0">
                    <p className="font-semibold text-warning-text text-sm mb-0.5">
                        Action Required — Rides Unassigned
                    </p>
                    <p className="text-sm text-warning-text/80">
                        {message}
                    </p>
                </div>
            </div>
        </div>
    )
}

export default RideCoverageWarning
