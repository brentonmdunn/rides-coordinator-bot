import { useState } from 'react'
import { useCopyToClipboard } from '../lib/utils'
import { Button } from './ui/button'
import { InfoToggleButton, InfoPanel } from './InfoHelp'
import RideTypeSelector, { type RideType } from './RideTypeSelector'
import PickupGroup from './PickupGroup'
import ErrorMessage from "./ErrorMessage"
import { usePickups } from '../hooks/usePickups'
import {
    ChannelIdField,
    MessageIdField,
    SectionCard,
    SettingsToggleButton,
} from './shared'

/**
 * A dashboard component that allows admins to lookup and display grouping locations
 * for a specific ride event (Friday, Sunday, or via a specific Discord message ID).
 */
function PickupLocations() {
    const [pickupRideType, setPickupRideType] = useState<RideType>('friday')
    const [messageId, setMessageId] = useState('')
    const [channelId, setChannelId] = useState('')
    const [showSettings, setShowSettings] = useState(false)
    const { copiedText: copiedUsername, copyToClipboard } = useCopyToClipboard()
    const [showInfo, setShowInfo] = useState(false)

    const {
        data: pickupData,
        error: pickupError,
        isLoading: pickupLoading,
        fetchPickups
    } = usePickups()

    const handleFetchPickups = async (e: React.FormEvent) => {
        e.preventDefault()
        await fetchPickups(pickupRideType, messageId, channelId)
    }

    return (
        <SectionCard
            icon="📍"
            title="List Pickups"
            actions={
                <>
                    <SettingsToggleButton
                        isOpen={showSettings}
                        onClick={() => setShowSettings(!showSettings)}
                    />
                    <InfoToggleButton
                        isOpen={showInfo}
                        onClick={() => setShowInfo(!showInfo)}
                        title="How to use List Pickups"
                    />
                </>
            }
        >
            <InfoPanel
                isOpen={showInfo}
                onClose={() => setShowInfo(false)}
                title="How to use List Pickups"
            >
                <ol className="list-decimal list-inside space-y-1.5">
                    <li>Select a <span className="font-medium">Ride Type</span> (e.g., Friday Fellowship).</li>
                    <li>If "Custom Message ID" is selected, copy & paste the Discord message ID.</li>
                    <li>Click <span className="font-medium">Fetch Pickups</span> to load the list.</li>
                    <li>Click on any person's name to copy their Discord username to your clipboard.</li>
                </ol>
            </InfoPanel>

            <form onSubmit={handleFetchPickups} className="space-y-6">
                {/* Ride Type Selection */}
                <RideTypeSelector value={pickupRideType} onChange={setPickupRideType} />

                {/* Message ID Input (only shown when message_id is selected) */}
                {pickupRideType === 'message_id' && (
                    <MessageIdField value={messageId} onChange={setMessageId} />
                )}

                {/* Advanced Settings (Channel ID) */}
                {showSettings && (
                    <ChannelIdField value={channelId} onChange={setChannelId} />
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
                    <div className="flex items-center justify-between mb-3">
                        <h3 className="text-lg font-semibold text-foreground">
                            Pickup Locations
                        </h3>
                        <span className="px-3 py-1 bg-muted text-muted-foreground text-sm font-medium rounded-full border border-border">
                            Total: {
                                Object.values(pickupData.housing_groups).reduce((acc, group) => acc + group.count, 0) +
                                (pickupData.unknown_users?.length || 0)
                            }
                        </span>
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
                        <div className="border border-warning rounded-lg overflow-hidden bg-warning/15">
                            <div className="px-4 py-3 border-b border-warning">
                                <h4 className="font-semibold text-foreground flex items-center gap-2">
                                    <span>⚠️</span>
                                    <span>Unknown Users</span>
                                    <span className="text-sm font-normal text-foreground/80">
                                        ({pickupData.unknown_users.length})
                                    </span>
                                    <span className="text-sm font-normal text-foreground/80"><em>Make sure their Discord username is correct in the Google sheet.</em></span>
                                </h4>
                            </div>
                            <div className="p-4">
                                <div className="text-foreground/80">
                                    {pickupData.unknown_users.join(', ')}
                                </div>
                            </div>
                        </div>
                    )}
                </div>
            )}
        </SectionCard>
    )
}

export default PickupLocations
