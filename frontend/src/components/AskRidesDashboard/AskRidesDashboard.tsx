import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '../../lib/api'
import ErrorMessage from "../ErrorMessage"
import type { AskRidesStatus } from '../../types'
import StatusCard from './StatusCard'
import { InfoToggleButton, InfoPanel } from '../InfoHelp'

import { Card, CardHeader, CardTitle, CardContent } from '../ui/card'

function AskRidesDashboard() {
    const [showInfo, setShowInfo] = useState(false)
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
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle><span>📅</span> Ask Rides Status Dashboard</CardTitle>
                <InfoToggleButton
                    isOpen={showInfo}
                    onClick={() => setShowInfo(!showInfo)}
                    title="About Dashboard Status"
                />
            </CardHeader>
            <CardContent>
                <InfoPanel
                    isOpen={showInfo}
                    onClose={() => setShowInfo(false)}
                    title="About Dashboard Status"
                >
                    <p className="mb-2">
                        This dashboard shows the current status of automated ride request jobs.
                    </p>
                    <ul className="space-y-1">
                        <li className="flex items-center gap-2">
                            <span className="w-2 h-2 rounded-full bg-green-500"></span>
                            <span><span className="font-medium">Will Send:</span> The job is scheduled and will run at the shown time.</span>
                        </li>
                        <li className="flex items-center gap-2">
                            <span className="w-2 h-2 rounded-full bg-yellow-500"></span>
                            <span><span className="font-medium">Will Not Send:</span> Feature is enabled, but no action is needed (e.g., no class scheduled).</span>
                        </li>
                        <li className="flex items-center gap-2">
                            <span className="w-2 h-2 rounded-full bg-red-500"></span>
                            <span><span className="font-medium">Disabled:</span> The feature flag for this job is turned off.</span>
                        </li>
                    </ul>
                </InfoPanel>

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
