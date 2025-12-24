import { useState } from 'react'
import { apiFetch } from '../lib/api'
import { Button } from './ui/button'
import { Input } from './ui/input'
import RideTypeSelector, { type RideType } from './RideTypeSelector'
import ErrorMessage from "./ErrorMessage"
import type { LocationData } from '../types'

import { Card, CardHeader, CardTitle, CardContent } from './ui/card'

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
        <Card>
            <CardHeader>
                <CardTitle><span>📍</span> List Pickups</CardTitle>
            </CardHeader>
            <CardContent>
                <form onSubmit={fetchPickups} className="space-y-6">
                    {/* Ride Type Selection */}
                    <RideTypeSelector value={pickupRideType} onChange={setPickupRideType} />

                    {/* Message ID Input (only shown when message_id is selected) */}
                    {pickupRideType === 'message_id' && (
                        <div className="p-4 bg-slate-50 dark:bg-zinc-800/50 rounded-lg border border-slate-100 dark:border-zinc-700">
                            <label className="block">
                                <span className="text-sm font-medium text-slate-700 dark:text-slate-300 mb-2 block">
                                    Message ID
                                </span>
                                <Input
                                    type="text"
                                    value={messageId}
                                    onChange={(e) => setMessageId(e.target.value)}
                                    placeholder="Enter Discord message ID"
                                    required
                                    className="w-full max-w-md"
                                />
                            </label>
                        </div>
                    )}

                    <div className="pt-2">
                        <Button
                            type="submit"
                            disabled={pickupLoading}
                            className="w-full sm:w-auto px-8 py-2.5 text-base font-semibold"
                        >
                            {pickupLoading ? 'Loading...' : 'Fetch Pickups'}
                        </Button>
                    </div>
                </form>

                {/* Error Display */}
                <div className="mt-6">
                    <ErrorMessage message={pickupError} />
                </div>

                {/* Raw Data Display */}
                {pickupData && (
                    <div className="mt-8">
                        <h3 className="text-lg font-semibold text-slate-900 dark:text-white mb-3">Raw Response</h3>
                        <div className="relative">
                            <pre className="p-4 bg-slate-900 text-slate-50 rounded-lg overflow-auto max-h-[500px] text-sm font-mono border border-slate-800 shadow-inner">
                                {JSON.stringify(pickupData, null, 2)}
                            </pre>
                            <div className="absolute top-0 right-0 p-2">
                                {/* Potentially add a copy button here for the JSON if needed later */}
                            </div>
                        </div>
                    </div>
                )}
            </CardContent>
        </Card>
    )
}

export default PickupLocations
