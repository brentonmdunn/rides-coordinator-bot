import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '../../lib/api'
import ErrorMessage from "../ErrorMessage"
import type { AskRidesStatus } from '../../types'
import StatusCard from './StatusCard'

import { Card, CardHeader, CardTitle, CardContent } from '../ui/card'

function AskRidesDashboard() {
    const {
        data: askRidesStatus,
        isLoading: askRidesLoading,
        error
    } = useQuery<AskRidesStatus>({
        queryKey: ['askRidesStatus'],
        queryFn: async () => {
            // ... unchanged
            const response = await apiFetch('/api/ask-rides/status')
            if (!response.ok) {
                throw new Error('Failed to load ask rides status')
            }
            return response.json()
        }
    })

    const askRidesError = error instanceof Error ? error.message : ''

    return (
        <Card>
            <CardHeader>
                <CardTitle><span>📅</span> Ask Rides Status Dashboard</CardTitle>
            </CardHeader>
            <CardContent>
                {askRidesLoading && (
                    <div className="p-8 text-center text-slate-500 animate-pulse">
                        Loading ask rides status...
                    </div>
                )}

                <div className="mb-6">
                    <ErrorMessage message={askRidesError} />
                </div>

                {!askRidesLoading && !askRidesError && askRidesStatus && (
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                        {/* Friday Fellowship */}
                        <StatusCard title="🎉 Friday Fellowship" job={askRidesStatus.friday} />

                        {/* Sunday Service */}
                        <StatusCard title="⛪ Sunday Service" job={askRidesStatus.sunday} />

                        {/* Sunday Class */}
                        <StatusCard title="📖 Sunday Class" job={askRidesStatus.sunday_class} />
                    </div>
                )}
            </CardContent>
        </Card>
    )
}

export default AskRidesDashboard
