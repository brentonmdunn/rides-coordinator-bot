import { useState } from 'react'
import { apiFetch } from '../lib/api'
import { copyToClipboard } from '../lib/utils'
import { Button } from './ui/button'
import { Input } from './ui/input'
import { InfoToggleButton, InfoPanel } from './InfoHelp'
import RideTypeSelector, { type RideType } from './RideTypeSelector'
import ErrorMessage from "./ErrorMessage"
import EditableOutput from './EditableOutput'
import type { GroupRidesResponse } from '../types'
import {
    ChannelIdField,
    LabeledField,
    MessageIdField,
    SectionCard,
    SettingsToggleButton,
} from './shared'

function GroupRides() {
    const [rideType, setRideType] = useState<RideType>('friday')
    const [groupMessageId, setGroupMessageId] = useState('')
    const [groupDriverCapacity, setGroupDriverCapacity] = useState('44444')
    const [channelId, setChannelId] = useState('')
    const [showSettings, setShowSettings] = useState(false)
    const [groupRidesSummary, setGroupRidesSummary] = useState<string | null>(null)
    const [groupRidesData, setGroupRidesData] = useState<string[] | null>(null)
    const [originalGroupRidesData, setOriginalGroupRidesData] = useState<string[] | null>(null)
    const [groupRidesError, setGroupRidesError] = useState<string>('')
    const [groupRidesLoading, setGroupRidesLoading] = useState(false)
    const [showInfo, setShowInfo] = useState(false)

    const groupRides = async (e: React.FormEvent) => {
        // ... implementation unchanged
        e.preventDefault()
        setGroupRidesLoading(true)
        setGroupRidesError('')
        setGroupRidesSummary(null)
        setGroupRidesData(null)
        setOriginalGroupRidesData(null)

        try {
            const body: Record<string, unknown> = {
                ride_type: rideType,
                message_id: rideType === 'message_id' ? groupMessageId : null,
                driver_capacity: groupDriverCapacity,
            }

            if (channelId) {
                body.channel_id = channelId
            }

            const response = await apiFetch('/api/group-rides', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body)
            })

            const data: GroupRidesResponse = await response.json()

            if (data.success && data.groupings) {
                setGroupRidesSummary(data.summary)
                setGroupRidesData(data.groupings)
                setOriginalGroupRidesData(data.groupings)
            } else {
                setGroupRidesError(data.error || 'Failed to group rides')
            }
        } catch (error) {
            setGroupRidesError(error instanceof Error ? error.message : 'Unknown error')
            console.error('Group rides error:', error)
        } finally {
            setGroupRidesLoading(false)
        }
    }

    const handleGroupingChange = (index: number, newValue: string) => {
        // ... unchanged
        if (!groupRidesData) return
        const newData = [...groupRidesData]
        newData[index] = newValue
        setGroupRidesData(newData)
    }

    const revertGrouping = (index: number) => {
        // ... unchanged
        if (!originalGroupRidesData || !groupRidesData) return
        const newData = [...groupRidesData]
        newData[index] = originalGroupRidesData[index]
        setGroupRidesData(newData)
    }

    return (
        <SectionCard
            icon="🚗"
            title="Group Rides"
            actions={
                <>
                    <SettingsToggleButton
                        isOpen={showSettings}
                        onClick={() => setShowSettings(!showSettings)}
                    />
                    <InfoToggleButton
                        isOpen={showInfo}
                        onClick={() => setShowInfo(!showInfo)}
                        title="How to use Group Rides"
                    />
                </>
            }
        >
            <InfoPanel
                isOpen={showInfo}
                onClose={() => setShowInfo(false)}
                title="How to use Group Rides"
            >
                <ol className="list-decimal list-inside space-y-1.5">
                    <li>Select a <span className="font-medium">Ride Type</span>.</li>
                    <li>Enter <span className="font-medium">Driver Capacity</span> using digits (e.g., "44444" means 5 drivers with 4 seats each).</li>
                    <li>Click <span className="font-medium">Group Rides</span> to generate assignments.</li>
                    <li>Use the text areas to manually adjust groupings if needed. <span className="font-medium">Revert</span> to revert to the original groupings.</li>
                    <li>Click <span className="font-medium">Copy</span> to copy the groupings to your clipboard.</li>
                </ol>
            </InfoPanel>
            <form onSubmit={groupRides} className="space-y-6">
                {/* Ride Type Selection */}
                <RideTypeSelector value={rideType} onChange={setRideType} />

                {/* Message ID Input (only shown when message_id is selected) */}
                {rideType === 'message_id' && (
                    <MessageIdField value={groupMessageId} onChange={setGroupMessageId} />
                )}

                {/* Driver Capacity */}
                <div>
                    <LabeledField label="Driver Capacity">
                        <div className="flex items-center gap-3">
                            <Input
                                type="text"
                                value={groupDriverCapacity}
                                onChange={(e) => setGroupDriverCapacity(e.target.value)}
                                placeholder="e.g., 44444"
                                className="w-32 font-mono"
                            />
                            <span className="text-sm text-muted-foreground">
                                (One digit per driver, e.g., "4" = 4 seats)
                            </span>
                        </div>
                    </LabeledField>
                </div>

                {/* Advanced Settings (Channel ID) */}
                {showSettings && (
                    <ChannelIdField value={channelId} onChange={setChannelId} />
                )}

                <div className="pt-2">
                    <Button
                        type="submit"
                        disabled={groupRidesLoading}
                        className="w-full sm:w-auto px-8 py-2.5 text-base font-semibold"
                    >
                        {groupRidesLoading ? 'Grouping Rides...' : 'Group Rides'}
                    </Button>
                </div>
            </form>

            {/* Loading Indicator */}
            {groupRidesLoading && (
                <div className="mt-6 p-4 bg-info/10 text-foreground rounded-lg flex items-start gap-3">
                    <div className="animate-spin text-xl">⏳</div>
                    <div>
                        <strong className="block font-semibold">Grouping rides...</strong>
                        <p className="text-sm mt-1 opacity-90">
                            This may take up to 60 seconds. Please wait...
                        </p>
                    </div>
                </div>
            )}

            {/* Error Display */}
            <div className="mt-6">
                <ErrorMessage message={groupRidesError} />
            </div>

            {/* Results Display */}
            {(groupRidesSummary || groupRidesData) && (
                <div className="mt-8 space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
                    {/* Summary Section */}
                    {groupRidesSummary && (
                        <div>
                            <h3 className="text-lg font-semibold text-foreground mb-3">Summary</h3>
                            <pre className="whitespace-pre-wrap break-all p-4 bg-success/15 text-foreground rounded-lg text-sm font-mono border border-success/30">
                                {groupRidesSummary}
                            </pre>
                        </div>
                    )}

                    {/* Individual Ride Groupings */}
                    {groupRidesData && (
                        <div>
                            <h3 className="text-lg font-semibold text-foreground mb-4">Ride Groupings</h3>
                            <div className="space-y-4">
                                {groupRidesData.map((grouping, index) => (
                                    <EditableOutput
                                        key={index}
                                        value={grouping}
                                        originalValue={originalGroupRidesData?.[index] || grouping}
                                        onChange={(newValue) => handleGroupingChange(index, newValue)}
                                        onCopy={() => copyToClipboard(grouping)}
                                        onRevert={() => revertGrouping(index)}
                                        minHeight="min-h-[60px]"
                                    />
                                ))}
                            </div>
                        </div>
                    )}
                </div>
            )}
        </SectionCard>
    )
}

export default GroupRides
