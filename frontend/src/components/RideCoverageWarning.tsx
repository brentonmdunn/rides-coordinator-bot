import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '../lib/api'
import type { RideCoverage } from '../types'
import { AlertTriangle } from 'lucide-react'

function RideCoverageWarning() {
    // Check Friday ride coverage
    const { data: fridayData } = useQuery<RideCoverage>({
        queryKey: ['rideCoverage', 'friday'],
        queryFn: async () => {
            const response = await apiFetch('/api/check-pickups/friday')
            if (!response.ok) {
                throw new Error('Failed to check Friday coverage')
            }
            return response.json()
        },
        staleTime: 5 * 60 * 1000,
        refetchOnWindowFocus: false,
        refetchOnMount: false,
        refetchOnReconnect: false,
    })

    // Check Sunday ride coverage
    const { data: sundayData } = useQuery<RideCoverage>({
        queryKey: ['rideCoverage', 'sunday'],
        queryFn: async () => {
            const response = await apiFetch('/api/check-pickups/sunday')
            if (!response.ok) {
                throw new Error('Failed to check Sunday coverage')
            }
            return response.json()
        },
        staleTime: 5 * 60 * 1000,
        refetchOnWindowFocus: false,
        refetchOnMount: false,
        refetchOnReconnect: false,
    })

    // Get current day and time
    const now = new Date()
    const day = now.getDay() // 0 = Sunday, 5 = Friday, 6 = Saturday
    const hour = now.getHours()

    // Check if we need to show warning for each ride type
    const fridayNeedsDrivers = fridayData?.message_found && !fridayData?.has_coverage_entries
    const sundayNeedsDrivers = sundayData?.message_found && !sundayData?.has_coverage_entries

    // Time-based conditions for showing warnings
    const shouldShowFridayWarning = fridayNeedsDrivers && day === 5 && hour >= 12 // Friday after 12pm
    const shouldShowSundayWarning = sundayNeedsDrivers && day === 6 && hour >= 17 // Saturday after 5pm

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
        <div className="p-4 bg-warning/15 border-l-4 border-warning rounded-md">
            <div className="flex items-start gap-3">
                <AlertTriangle className="h-5 w-5 text-warning-text flex-shrink-0 mt-0.5" />
                <div>
                    <h3 className="font-semibold text-warning-text mb-1">
                        ⚠️ Rides Needed
                    </h3>
                    <p className="text-sm text-warning-text">
                        {message}
                    </p>
                </div>
            </div>
        </div>
    )
}

export default RideCoverageWarning
