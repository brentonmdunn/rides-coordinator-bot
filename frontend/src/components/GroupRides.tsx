import { useState } from 'react'
import { apiFetch } from '../lib/api'
import { Button } from './ui/button'
import { Input } from './ui/input'
import RideTypeSelector, { type RideType } from './RideTypeSelector'
import ErrorMessage from "./ErrorMessage"
import type { GroupRidesResponse } from '../types'

function GroupRides() {
    const [rideType, setRideType] = useState<RideType>('friday')
    const [groupMessageId, setGroupMessageId] = useState('')
    const [groupDriverCapacity, setGroupDriverCapacity] = useState('44444')
    const [channelId] = useState('939950319721406464')
    const [groupRidesSummary, setGroupRidesSummary] = useState<string | null>(null)
    const [groupRidesData, setGroupRidesData] = useState<string[] | null>(null)
    const [groupRidesError, setGroupRidesError] = useState<string>('')
    const [groupRidesLoading, setGroupRidesLoading] = useState(false)
    const [copiedIndex, setCopiedIndex] = useState<number | null>(null)

    const groupRides = async (e: React.FormEvent) => {
        e.preventDefault()
        setGroupRidesLoading(true)
        setGroupRidesError('')
        setGroupRidesSummary(null)
        setGroupRidesData(null)

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
            setCopiedIndex(index)
            // Reset after 5 seconds
            setTimeout(() => setCopiedIndex(null), 5000)
        } catch (error) {
            console.error('Failed to copy:', error)
            alert('Failed to copy to clipboard')
        }
    }

    return (
        <div className="card" style={{ marginBottom: '2em', textAlign: 'left' }}>
            <h2>🚗 Group Rides</h2>
            <form onSubmit={groupRides} style={{ marginBottom: '1em' }}>
                {/* Ride Type Selection */}
                <RideTypeSelector value={rideType} onChange={setRideType} />

                {/* Message ID Input (only shown when message_id is selected) */}
                {rideType === 'message_id' && (
                    <div style={{ marginBottom: '1em', padding: '1em', background: '#f9fafb', borderRadius: '8px' }}>
                        <label>
                            Message ID:
                            <Input
                                type="text"
                                value={groupMessageId}
                                onChange={(e) => setGroupMessageId(e.target.value)}
                                placeholder="Enter Discord message ID"
                                required
                                style={{ marginLeft: '0.5em', padding: '0.5em', width: '300px' }}
                            />
                        </label>
                    </div>
                )}

                {/* Driver Capacity */}
                <div style={{ marginBottom: '1.5em' }}>
                    <label>
                        Driver Capacity:
                        <Input
                            type="text"
                            value={groupDriverCapacity}
                            onChange={(e) => setGroupDriverCapacity(e.target.value)}
                            placeholder="e.g., 44444"
                            style={{ marginLeft: '0.5em', padding: '0.5em', width: '150px' }}
                        />
                        <span style={{ marginLeft: '0.5em', fontSize: '0.9em', color: '#6b7280' }}>
                            (One digit per driver, e.g., "44444" = 5 drivers with 4 seats each)
                        </span>
                    </label>
                </div>

                <Button type="submit" disabled={groupRidesLoading} style={{
                    padding: '0.75em 1.5em',
                    fontSize: '1em',
                    fontWeight: 'bold'
                }}>
                    {groupRidesLoading ? 'Grouping Rides...' : 'Group Rides'}
                </Button>
            </form>

            {/* Loading Indicator */}
            {groupRidesLoading && (
                <div style={{
                    padding: '1em',
                    background: '#e3f2fd',
                    borderRadius: '4px',
                    marginBottom: '1em',
                    color: '#1976d2'
                }}>
                    <strong>⏳ Grouping rides...</strong>
                    <p style={{ margin: '0.5em 0 0 0', fontSize: '0.9em' }}>
                        This may take 15-30 seconds. Please wait...
                    </p>
                </div>
            )}

            {/* Error Display */}
            <ErrorMessage message={groupRidesError} />

            {/* Results Display */}
            {(groupRidesSummary || groupRidesData) && (
                <div style={{ marginTop: '1em' }}>
                    {/* Summary Section */}
                    {groupRidesSummary && (
                        <div style={{ marginBottom: '1.5em' }}>
                            <h3>Summary:</h3>
                            <pre style={{
                                whiteSpace: 'pre-wrap',
                                wordWrap: 'break-word',
                                padding: '1em',
                                background: '#e8f5e9',
                                borderRadius: '4px',
                                fontSize: '0.9em',
                                fontFamily: 'monospace',
                                border: '1px solid #4caf50'
                            }}>
                                {groupRidesSummary}
                            </pre>
                        </div>
                    )}

                    {/* Individual Ride Groupings */}
                    {groupRidesData && (
                        <>
                            <h3>Ride Groupings:</h3>
                            {groupRidesData.map((grouping, index) => (
                                <div
                                    key={index}
                                    style={{
                                        marginBottom: '1em',
                                        padding: '1em',
                                        background: '#f5f5f5',
                                        borderRadius: '4px',
                                        position: 'relative'
                                    }}
                                >
                                    <Button
                                        onClick={() => copyToClipboard(grouping, index)}
                                        style={{
                                            position: 'absolute',
                                            top: '0.5em',
                                            right: '0.5em',
                                            padding: '0.25em 0.5em',
                                            fontSize: '0.85em'
                                        }}
                                    >
                                        {copiedIndex === index ? '✓ Copied!' : '📋 Copy'}
                                    </Button>
                                    <pre style={{
                                        whiteSpace: 'pre-wrap',
                                        wordWrap: 'break-word',
                                        margin: 0,
                                        paddingRight: '5em',
                                        fontSize: '0.9em',
                                        fontFamily: 'monospace'
                                    }}>
                                        {grouping}
                                    </pre>
                                </div>
                            ))}
                        </>
                    )}
                </div>
            )}
        </div>
    )
}

export default GroupRides
