import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '../../lib/api'
import ErrorMessage from "../ErrorMessage"
import type { AskRidesStatus } from '../../types'
import StatusCard from './StatusCard'

function AskRidesDashboard() {
    const {
        data: askRidesStatus,
        isLoading: askRidesLoading,
        error
    } = useQuery<AskRidesStatus>({
        queryKey: ['askRidesStatus'],
        queryFn: async () => {
            const response = await apiFetch('/api/ask-rides/status')
            if (!response.ok) {
                throw new Error('Failed to load ask rides status')
            }
            return response.json()
        }
    })

    const askRidesError = error instanceof Error ? error.message : ''

    return (
        <div className="card" style={{ marginTop: '2em', textAlign: 'left' }}>
            <h2>📅 Ask Rides Status Dashboard</h2>

            {askRidesLoading && <p>Loading ask rides status...</p>}

            <ErrorMessage message={askRidesError} />

            {!askRidesLoading && !askRidesError && askRidesStatus && (
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '1em', marginTop: '1em' }}>
                    {/* Friday Fellowship */}
                    <StatusCard title="🎉 Friday Fellowship" job={askRidesStatus.friday} />

                    {/* Sunday Service */}
                    <StatusCard title="⛪ Sunday Service" job={askRidesStatus.sunday} />

                    {/* Sunday Class */}
                    <StatusCard title="📖 Sunday Class" job={askRidesStatus.sunday_class} />
                </div>
            )}
        </div>
    )
}

export default AskRidesDashboard
