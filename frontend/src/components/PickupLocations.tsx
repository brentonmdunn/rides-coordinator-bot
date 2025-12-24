import { useState } from 'react'
import { apiFetch } from '../lib/api'
import { Button } from './ui/button'
import { Input } from './ui/input'
import RideTypeSelector, { type RideType } from './RideTypeSelector'
import ErrorMessage from "./ErrorMessage"
import type { LocationData } from '../types'

function PickupLocations() {
    const [pickupRideType, setPickupRideType] = useState<RideType>('friday')
    const [messageId, setMessageId] = useState('')
    const [channelId] = useState('939950319721406464')
    const [pickupData, setPickupData] = useState<LocationData | null>(null)
    const [pickupError, setPickupError] = useState<string>('')
    const [pickupLoading, setPickupLoading] = useState(false)

    const fetchPickups = async (e: React.FormEvent) => {
        e.preventDefault()
        setPickupLoading(true)
        setPickupError('')
        setPickupData(null)

        try {
            const response = await apiFetch('/api/list-pickups', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    ride_type: pickupRideType,
                    message_id: pickupRideType === 'message_id' ? messageId : null,
                    channel_id: channelId
                })
            })

            const result = await response.json()

            if (result.success && result.data) {
                setPickupData(result.data)
            } else {
                setPickupError(result.error || 'Failed to fetch pickups')
            }
        } catch (error) {
            setPickupError(error instanceof Error ? error.message : 'Unknown error')
            console.error('Pickup fetch error:', error)
        } finally {
            setPickupLoading(false)
        }
    }

    return (
        <div className="card" style={{ marginBottom: '2em', textAlign: 'left' }}>
            <h2>📍 List Pickups</h2>
            <form onSubmit={fetchPickups} style={{ marginBottom: '1em' }}>
                {/* Ride Type Selection */}
                <RideTypeSelector value={pickupRideType} onChange={setPickupRideType} />

                {/* Message ID Input (only shown when message_id is selected) */}
                {pickupRideType === 'message_id' && (
                    <div style={{ marginBottom: '1em', padding: '1em', background: '#f9fafb', borderRadius: '8px' }}>
                        <label>
                            Message ID:
                            <Input
                                type="text"
                                value={messageId}
                                onChange={(e) => setMessageId(e.target.value)}
                                placeholder="Enter Discord message ID"
                                required
                                style={{ marginLeft: '0.5em', padding: '0.5em', width: '300px' }}
                            />
                        </label>
                    </div>
                )}

                <Button type="submit" disabled={pickupLoading} style={{
                    padding: '0.75em 1.5em',
                    fontSize: '1em',
                    fontWeight: 'bold'
                }}>
                    {pickupLoading ? 'Loading...' : 'Fetch Pickups'}
                </Button>
            </form>

            {/* Error Display */}
            <ErrorMessage message={pickupError} />

            {/* Raw Data Display */}
            {pickupData && (
                <div style={{ marginTop: '1em' }}>
                    <h3>Raw Response:</h3>
                    <pre style={{
                        background: '#f5f5f5',
                        padding: '1em',
                        borderRadius: '4px',
                        overflow: 'auto',
                        maxHeight: '500px',
                        textAlign: 'left',
                        fontSize: '0.9em'
                    }}>
                        {JSON.stringify(pickupData, null, 2)}
                    </pre>
                </div>
            )}
        </div>
    )
}

export default PickupLocations
