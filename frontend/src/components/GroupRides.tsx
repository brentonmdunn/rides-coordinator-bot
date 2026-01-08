import { useState } from 'react'
import { apiFetch } from '../lib/api'
import { Button } from './ui/button'
import { Input } from './ui/input'
import { InfoToggleButton, InfoPanel } from './InfoHelp'
import RideTypeSelector, { type RideType } from './RideTypeSelector'
import ErrorMessage from "./ErrorMessage"
import EditableOutput from './EditableOutput'
import type { GroupRidesResponse } from '../types'

import { Card, CardHeader, CardTitle, CardContent } from './ui/card'
import { Settings } from 'lucide-react'

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
    const [copiedGrouping, setCopiedGrouping] = useState<number | null>(null)
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
            const body: any = {
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

    const copyToClipboard = async (text: string, index: number) => {
        try {
            await navigator.clipboard.writeText(text)
            setCopiedGrouping(index)
            setTimeout(() => setCopiedGrouping(null), 5000)
        } catch (error) {
            console.error('Failed to copy:', error)
            alert('Failed to copy to clipboard')
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
        <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle><span>🚗</span> Group Rides</CardTitle>
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
                        title="How to use Group Rides"
                    />
                </div>
            </CardHeader>
            <CardContent>
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
                        <div className="p-4 bg-slate-50 dark:bg-zinc-800/50 rounded-lg border border-slate-100 dark:border-zinc-700">
                            <label className="block">
                                <span className="text-sm font-medium text-slate-700 dark:text-slate-300 mb-2 block">
                                    Message ID
                                </span>
                                <Input
                                    type="text"
                                    value={groupMessageId}
                                    onChange={(e) => setGroupMessageId(e.target.value)}
                                    placeholder="Enter Discord message ID"
                                    required
                                    className="w-full max-w-md"
                                />
                            </label>
                        </div>
                    )}

                    {/* Driver Capacity */}
                    <div>
                        <label className="block">
                            <span className="text-sm font-medium text-slate-700 dark:text-slate-300 mb-2 block">
                                Driver Capacity
                            </span>
                            <div className="flex items-center gap-3">
                                <Input
                                    type="text"
                                    value={groupDriverCapacity}
                                    onChange={(e) => setGroupDriverCapacity(e.target.value)}
                                    placeholder="e.g., 44444"
                                    className="w-32 font-mono"
                                />
                                <span className="text-sm text-slate-500 dark:text-slate-400">
                                    (One digit per driver, e.g., "4" = 4 seats)
                                </span>
                            </div>
                        </label>
                    </div>

                    {/* Advanced Settings (Channel ID) */}
                    {showSettings && (
                        <div className="p-4 bg-slate-50 dark:bg-zinc-800/50 rounded-lg border border-slate-100 dark:border-zinc-700 animate-in fade-in slide-in-from-top-2">
                            <label className="block">
                                <span className="text-sm font-medium text-slate-700 dark:text-slate-300 mb-2 block">
                                    Custom Channel ID (Optional)
                                </span>
                                <Input
                                    type="text"
                                    value={channelId}
                                    onChange={(e) => setChannelId(e.target.value)}
                                    placeholder="Default: Rides Announcements Channel"
                                    className="w-full max-w-md font-mono text-sm"
                                />
                                <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
                                    Leave blank to use the default channel.
                                </p>
                            </label>
                        </div>
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
                    <div className="mt-6 p-4 bg-blue-50 dark:bg-blue-950/30 text-blue-700 dark:text-blue-300 rounded-lg flex items-start gap-3">
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
                                <h3 className="text-lg font-semibold text-slate-900 dark:text-white mb-3">Summary</h3>
                                <pre className="whitespace-pre-wrap break-all p-4 bg-emerald-50 dark:bg-emerald-950/20 text-emerald-900 dark:text-emerald-100 rounded-lg text-sm font-mono border border-emerald-100 dark:border-emerald-900/50">
                                    {groupRidesSummary}
                                </pre>
                            </div>
                        )}

                        {/* Individual Ride Groupings */}
                        {groupRidesData && (
                            <div>
                                <h3 className="text-lg font-semibold text-slate-900 dark:text-white mb-4">Ride Groupings</h3>
                                <div className="space-y-4">
                                    {groupRidesData.map((grouping, index) => (
                                        <EditableOutput
                                            key={index}
                                            value={grouping}
                                            originalValue={originalGroupRidesData?.[index] || grouping}
                                            onChange={(newValue) => handleGroupingChange(index, newValue)}
                                            onCopy={() => copyToClipboard(grouping, index)}
                                            onRevert={() => revertGrouping(index)}
                                            copied={copiedGrouping === index}
                                            minHeight="min-h-[60px]"
                                        />
                                    ))}
                                </div>
                            </div>
                        )}
                    </div>
                )}
            </CardContent>
        </Card>
    )
}

export default GroupRides
