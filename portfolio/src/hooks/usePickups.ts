import { useState } from 'react'
import { apiFetch } from '../lib/api'
import type { LocationData } from '../types'
import type { RideType } from '../components/RideTypeSelector'

/**
 * Hook to manage fetching and storing pickup locations from the backend.
 * Encapsulates the network request and loading/error states.
 */
export function usePickups() {
    const [data, setData] = useState<LocationData | null>(null)
    const [error, setError] = useState<string>('')
    const [isLoading, setIsLoading] = useState(false)

    /**
     * Fetches pickup locations from the API.
     *
     * @param rideType - The type of ride (e.g., 'friday', 'sunday', or 'message_id')
     * @param messageId - Required if rideType is 'message_id' to lookup specific Discord message
     * @param channelId - Optional custom channel ID to search in
     * @returns A promise that resolves when the fetch completes
     */
    const fetchPickups = async (
        rideType: RideType,
        messageId: string,
        channelId: string | undefined
    ) => {
        setIsLoading(true)
        setError('')
        setData(null)

        try {
            const body: Record<string, unknown> = {
                ride_type: rideType,
                message_id: rideType === 'message_id' ? messageId : null,
            }

            if (channelId) {
                body.channel_id = channelId
            }

            const response = await apiFetch('/api/list-pickups', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body)
            })

            const result = await response.json()

            if (result.success && result.data) {
                setData(result.data)
            } else {
                setError(result.error || 'Failed to fetch pickups')
            }
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Unknown error')
            console.error('Pickup fetch error:', err)
        } finally {
            setIsLoading(false)
        }
    }

    return {
        data,
        error,
        isLoading,
        fetchPickups,
        clearData: () => setData(null)
    }
}
