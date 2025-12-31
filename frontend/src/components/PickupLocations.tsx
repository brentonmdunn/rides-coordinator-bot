import { useState } from 'react'
import { apiFetch } from '../lib/api'
import { Button } from './ui/button'
import { Input } from './ui/input'
import { InfoToggleButton, InfoPanel } from './InfoHelp'
import RideTypeSelector, { type RideType } from './RideTypeSelector'
import PickupGroup from './PickupGroup'
import { Section, Label, StatusMessage, Badge } from './design-system'
import type { LocationData } from '../types'

import { Card, CardHeader, CardTitle, CardContent } from './ui/card'
import { Settings } from 'lucide-react'

function PickupLocations() {
    const [pickupRideType, setPickupRideType] = useState<RideType>('friday')
    const [messageId, setMessageId] = useState('')
    const [channelId, setChannelId] = useState('')
    const [showSettings, setShowSettings] = useState(false)
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
            const body: any = {
                ride_type: pickupRideType,
                message_id: pickupRideType === 'message_id' ? messageId : null,
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
                <div className="flex items-center gap-2">
                    <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => setShowSettings(!showSettings)}
                        className={`h-8 w-8 transition-colors ${showSettings
                            ? 'bg-slate-100 text-slate-900 dark:bg-slate-800 dark:text-slate-100'
                            : 'text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200'
                            }`}
                        title="Advanced Settings"
                    >
                        <Settings className="h-4 w-4" />
                    </Button>
                    <InfoToggleButton
                        isOpen={showInfo}
                        onClick={() => setShowInfo(!showInfo)}
                        title="How to use List Pickups"
                    />
                </div>
            </CardHeader>
            <CardContent>
                <InfoPanel
                    isOpen={showInfo}
                    onClose={() => setShowInfo(false)}
                    title="How to use List Pickups"
                >
                    <ol className="list-decimal list-inside space-y-1.5">
                        <li>Select a <span className="font-medium">Ride Type</span> (e.g., Friday Service).</li>
                        <li>If "By Message ID" is selected, copy & paste the Discord message ID.</li>
                        <li>Click <span className="font-medium">Fetch Pickups</span> to load the list.</li>
                        <li>Click on any person's name to copy their Discord username to your clipboard.</li>
                    </ol>
                </InfoPanel>

                <form onSubmit={fetchPickups} className="space-y-6">
                    {/* Ride Type Selection */}
                    <RideTypeSelector value={pickupRideType} onChange={setPickupRideType} />

                    {/* Message ID Input (only shown when message_id is selected) */}
                    {pickupRideType === 'message_id' && (
                        <Section variant="muted">
                            <Label htmlFor="message-id">Message ID</Label>
                            <Input
                                id="message-id"
                                type="text"
                                value={messageId}
                                onChange={(e) => setMessageId(e.target.value)}
                                placeholder="Enter Discord message ID"
                                required
                                className="w-full max-w-md"
                            />
                        </Section>
                    )}

                    {/* Advanced Settings (Channel ID) */}
                    {showSettings && (
                        <Section variant="muted" className="animate-in fade-in slide-in-from-top-2">
                            <Label htmlFor="channel-id">Custom Channel ID (Optional)</Label>
                            <Input
                                id="channel-id"
                                type="text"
                                value={channelId}
                                onChange={(e) => setChannelId(e.target.value)}
                                placeholder="Default: Rides Announcements Channel"
                                className="w-full max-w-md font-mono text-sm"
                            />
                            <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
                                Leave blank to use the default channel.
                            </p>
                        </Section>
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
                {pickupError && (
                    <div className="mt-6">
                        <StatusMessage variant="error">{pickupError}</StatusMessage>
                    </div>
                )}

                {/* Pickup Locations Display */}
                {pickupData && (
                    <div className="mt-8 space-y-6">
                        <div className="flex items-center justify-between mb-3">
                            <h3 className="text-lg font-semibold text-slate-900 dark:text-white">
                                Pickup Locations
                            </h3>
                            <Badge rounded="full" size="lg">
                                Total: {
                                    Object.values(pickupData.housing_groups).reduce((acc, group) => acc + group.count, 0) +
                                    (pickupData.unknown_users?.length || 0)
                                }
                            </Badge>
                        </div>

                        {/* Housing Groups */}
                        <div className="space-y-6">
                            {Object.entries(pickupData.housing_groups).map(([groupName, groupData]) => (
                                <PickupGroup
                                    key={groupName}
                                    groupName={groupName}
                                    groupData={groupData}
                                    copiedUsername={copiedUsername}
                                    onCopy={copyToClipboard}
                                />
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
                                        <span className="text-sm font-normal text-amber-700 dark:text-amber-400"><em>Make sure their Discord username is correct in the Google sheet.</em></span>
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
