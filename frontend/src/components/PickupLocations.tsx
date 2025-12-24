import { useState } from 'react'
import { apiFetch } from '../lib/api'
import { Button } from './ui/button'
import { Input } from './ui/input'
import { Info, X } from 'lucide-react'
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
    const [copiedUsername, setCopiedUsername] = useState<string | null>(null)
    const [showInfo, setShowInfo] = useState(false)

    const copyToClipboard = async (discordUsername: string | null) => {
        if (!discordUsername) return

        try {
            await navigator.clipboard.writeText(discordUsername)
            setCopiedUsername(discordUsername)
            setTimeout(() => setCopiedUsername(null), 2000)
        } catch (error) {
            console.error('Failed to copy to clipboard:', error)
        }
    }

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
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="flex items-center gap-2">
                    <span>📍</span>
                    <span>List Pickups</span>
                </CardTitle>
                <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => setShowInfo(!showInfo)}
                    className="h-8 w-8 text-slate-500 hover:text-slate-900 dark:text-slate-400 dark:hover:text-slate-100"
                    title="How to use"
                >
                    <Info className="h-5 w-5" />
                    <span className="sr-only">How to use</span>
                </Button>
            </CardHeader>
            <CardContent>
                {showInfo && (
                    <div className="mb-6 p-4 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg relative">
                        <button
                            onClick={() => setShowInfo(false)}
                            className="absolute top-2 right-2 text-blue-400 hover:text-blue-600 dark:text-blue-400 dark:hover:text-blue-300 transition-colors"
                        >
                            <X className="h-4 w-4" />
                            <span className="sr-only">Close info</span>
                        </button>
                        <h4 className="font-semibold text-blue-900 dark:text-blue-300 mb-2 text-sm flex items-center gap-2">
                            <Info className="h-4 w-4" />
                            How to use List Pickups
                        </h4>
                        <ol className="list-decimal list-inside space-y-1.5 text-sm text-blue-800 dark:text-blue-200 ml-1">
                            <li>Select a <span className="font-medium">Ride Type</span> (e.g., Friday Service).</li>
                            <li>If "By Message ID" is selected, copy & paste the Discord message ID.</li>
                            <li>Click <span className="font-medium">Fetch Pickups</span> to load the list.</li>
                            <li>Click on any person's name to copy their Discord username to your clipboard.</li>
                        </ol>
                    </div>
                )}

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

                {/* Pickup Locations Display */}
                {pickupData && (
                    <div className="mt-8 space-y-6">
                        <h3 className="text-lg font-semibold text-slate-900 dark:text-white mb-3">Pickup Locations</h3>

                        {/* Housing Groups */}
                        <div className="space-y-6">
                            {Object.entries(pickupData.housing_groups).map(([groupName, groupData]) => (
                                <div key={groupName} className="border border-slate-200 dark:border-zinc-700 rounded-lg overflow-hidden">
                                    {/* Group Header */}
                                    <div className="bg-slate-100 dark:bg-zinc-800 px-4 py-3 border-b border-slate-200 dark:border-zinc-700">
                                        <h4 className="font-semibold text-slate-900 dark:text-white flex items-center gap-2">
                                            <span>{groupData.emoji}</span>
                                            <span className="capitalize">{groupName}</span>
                                            <span className="text-sm font-normal text-slate-600 dark:text-slate-400">
                                                ({groupData.count} {groupData.count === 1 ? 'person' : 'people'})
                                            </span>
                                        </h4>
                                    </div>

                                    {/* Locations within this group */}
                                    <div className="divide-y divide-slate-200 dark:divide-zinc-700">
                                        {Object.entries(groupData.locations).map(([locationName, people]) => (
                                            <div key={locationName} className="p-4 bg-white dark:bg-zinc-900">
                                                <div className="capitalize font-medium text-slate-800 dark:text-slate-200 mb-2">
                                                    {locationName}:
                                                </div>
                                                <div className="text-slate-600 dark:text-slate-400 ml-4">
                                                    {people.map((person, idx) => (
                                                        <span key={idx}>
                                                            {person.discord_username ? (
                                                                <button
                                                                    onClick={() => copyToClipboard(person.discord_username)}
                                                                    className={`hover:text-blue-600 dark:hover:text-blue-400 hover:underline cursor-pointer transition-colors ${copiedUsername === person.discord_username
                                                                        ? 'text-green-600 dark:text-green-400 font-medium'
                                                                        : ''
                                                                        }`}
                                                                    title={`Click to copy @${person.discord_username}`}
                                                                >
                                                                    {person.name}
                                                                    {copiedUsername === person.discord_username && ' ✓'}
                                                                </button>
                                                            ) : (
                                                                <span>{person.name}</span>
                                                            )}
                                                            {idx < people.length - 1 ? ', ' : ''}
                                                        </span>
                                                    ))}
                                                    {people.length === 0 && (
                                                        <span className="italic text-slate-400 dark:text-slate-500">No one</span>
                                                    )}
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            ))}
                        </div>

                        {/* Unknown Users */}
                        {pickupData.unknown_users && pickupData.unknown_users.length > 0 && (
                            <div className="border border-amber-200 dark:border-amber-800 rounded-lg overflow-hidden bg-amber-50 dark:bg-amber-950/30">
                                <div className="px-4 py-3 border-b border-amber-200 dark:border-amber-800">
                                    <h4 className="font-semibold text-amber-900 dark:text-amber-200 flex items-center gap-2">
                                        <span>⚠️</span>
                                        <span>Unknown Users</span>
                                        <span className="text-sm font-normal text-amber-700 dark:text-amber-400">
                                            ({pickupData.unknown_users.length})
                                        </span>
                                    </h4>
                                </div>
                                <div className="p-4">
                                    <div className="text-amber-800 dark:text-amber-300">
                                        {pickupData.unknown_users.join(', ')}
                                    </div>
                                </div>
                            </div>
                        )}
                    </div>
                )}
            </CardContent>
        </Card>
    )
}

export default PickupLocations
