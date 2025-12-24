import { useState } from 'react'
import { apiFetch } from '../lib/api'
import { Button } from './ui/button'
import { Input } from './ui/input'
import { InfoToggleButton, InfoPanel } from './InfoHelp'
import RideTypeSelector, { type RideType } from './RideTypeSelector'
import ErrorMessage from "./ErrorMessage"
import type { GroupRidesResponse } from '../types'

import { Card, CardHeader, CardTitle, CardContent } from './ui/card'

function GroupRides() {
    // ... state hooks (unchanged)

    const [rideType, setRideType] = useState<RideType>('friday')
    const [groupMessageId, setGroupMessageId] = useState('')
    const [groupDriverCapacity, setGroupDriverCapacity] = useState('44444')
    const [channelId] = useState('939950319721406464')
    const [groupRidesSummary, setGroupRidesSummary] = useState<string | null>(null)
    const [groupRidesData, setGroupRidesData] = useState<string[] | null>(null)
    const [originalGroupRidesData, setOriginalGroupRidesData] = useState<string[] | null>(null)
    const [groupRidesError, setGroupRidesError] = useState<string>('')
    const [groupRidesLoading, setGroupRidesLoading] = useState(false)
    const [copiedIndex, setCopiedIndex] = useState<number | null>(null)
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
            const response = await apiFetch('/api/group-rides', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    ride_type: rideType,
                    message_id: rideType === 'message_id' ? groupMessageId : null,
                    driver_capacity: groupDriverCapacity,
                    channel_id: channelId
                })
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
        // ... unchanged
        try {
            await navigator.clipboard.writeText(text)
            setCopiedIndex(index)
            setTimeout(() => setCopiedIndex(null), 5000)
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
                <InfoToggleButton
                    isOpen={showInfo}
                    onClick={() => setShowInfo(!showInfo)}
                    title="How to use Group Rides"
                />
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
                        <li>Use the text areas to manually adjust groupings if needed.</li>
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
                                This may take 15-30 seconds. Please wait...
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
                                <pre className="whitespace-pre-wrap p-4 bg-emerald-50 dark:bg-emerald-950/20 text-emerald-900 dark:text-emerald-100 rounded-lg text-sm font-mono border border-emerald-100 dark:border-emerald-900/50">
                                    {groupRidesSummary}
                                </pre>
                            </div>
                        )}

                        {/* Individual Ride Groupings */}
                        {groupRidesData && (
                            <div>
                                <h3 className="text-lg font-semibold text-slate-900 dark:text-white mb-4">Ride Groupings</h3>
                                <div className="space-y-4">
                                    {groupRidesData.map((grouping, index) => {
                                        const isModified = originalGroupRidesData && originalGroupRidesData[index] !== grouping;
                                        return (
                                            <div
                                                key={index}
                                                className="group relative bg-slate-50 dark:bg-zinc-800/50 rounded-lg border border-slate-200 dark:border-zinc-700 p-1 transition-all hover:shadow-md hover:border-slate-300 dark:hover:border-zinc-600"
                                            >
                                                <div className="absolute top-2 right-2 z-10 flex gap-2 opacity-100 sm:opacity-0 sm:group-hover:opacity-100 transition-opacity">
                                                    {isModified && (
                                                        <Button
                                                            onClick={() => revertGrouping(index)}
                                                            variant="outline"
                                                            size="sm"
                                                            className="h-8 px-2 text-xs border-amber-200 text-amber-700 hover:bg-amber-50 hover:text-amber-800 bg-white"
                                                        >
                                                            ↩ Revert
                                                        </Button>
                                                    )}
                                                    <Button
                                                        onClick={() => copyToClipboard(grouping, index)}
                                                        size="sm"
                                                        variant={copiedIndex === index ? "default" : "outline"}
                                                        className={`h-8 px-2 text-xs bg-white hover:bg-slate-100 ${copiedIndex === index ? "bg-emerald-600 hover:bg-emerald-700 text-white border-transparent" : "text-slate-700"}`}
                                                    >
                                                        {copiedIndex === index ? '✓ Copied' : '📋 Copy'}
                                                    </Button>
                                                </div>
                                                <textarea
                                                    value={grouping}
                                                    onChange={(e) => handleGroupingChange(index, e.target.value)}
                                                    className="w-full min-h-[60px] p-4 text-sm font-mono bg-transparent border-0 resize-y focus:ring-0 focus:outline-none text-slate-800 dark:text-slate-200 rounded-md"
                                                    spellCheck={false}
                                                />
                                            </div>
                                        )
                                    })}
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
