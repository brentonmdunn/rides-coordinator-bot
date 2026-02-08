import { useState, useEffect } from 'react'
import { apiFetch } from '../lib/api'
import { Card, CardHeader, CardTitle, CardContent } from './ui/card'
import { Button } from './ui/button'
import { RefreshCw } from 'lucide-react'
import { InfoToggleButton, InfoPanel } from './InfoHelp'
import ErrorMessage from "./ErrorMessage"
import type { AskRidesReactionsData } from '../types'
import { UsernamePill } from './UsernamePill'


type MessageType = 'friday' | 'sunday' | 'sunday_class'

interface MessageTypeOption {
    value: MessageType
    label: string
    emoji: string
}

const MESSAGE_TYPES: MessageTypeOption[] = [
    { value: 'friday', label: 'Friday Fellowship', emoji: '🎉' },
    { value: 'sunday', label: 'Sunday Service', emoji: '⛪' },
    { value: 'sunday_class', label: 'Sunday Class', emoji: '📖' }
]

function ReactionDetails() {
    const [data, setData] = useState<AskRidesReactionsData | null>(null)
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState('')
    const [selectedType, setSelectedType] = useState<MessageType>('friday')
    const [manualOverride, setManualOverride] = useState(false)
    const [showInfo, setShowInfo] = useState(false)

    const getAutomaticDay = (): MessageType => {
        const now = new Date()
        const day = now.getDay()
        const hour = now.getHours()

        // Default to Sunday if it's Saturday (6) or Sunday (0)
        // OR if it's Friday (5) after 10pm
        if (day === 6 || day === 0 || (day === 5 && hour >= 22)) {
            return 'sunday'
        }
        // Otherwise default to Friday
        // Note: Never automatically defaults to 'sunday_class' as requested
        return 'friday'
    }

    const fetchDataForType = async (messageType: MessageType) => {
        setLoading(true)
        setError('')
        try {
            const response = await apiFetch(`/api/ask-rides/reactions/${messageType}`)
            if (!response.ok) {
                // If the specific type (e.g. Sunday) isn't found, we don't auto-switch to others
                // to avoid confusing behavior, just show the "not found" state.
                if (response.status === 404) {
                    setData({
                        message_type: messageType,
                        reactions: {},
                        username_to_name: {},
                        message_found: false
                    })
                    setSelectedType(messageType)
                    return
                }
                throw new Error('Failed to fetch ask-rides reactions')
            }
            const result = await response.json()
            setData(result)
            setSelectedType(messageType)
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Unknown error')
        } finally {
            setLoading(false)
        }
    }

    const updateTypeAndFetch = async () => {
        const currentType = getAutomaticDay()
        setManualOverride(false)
        await fetchDataForType(currentType)
    }

    const handleTypeChange = async (messageType: MessageType) => {
        // Set manual override when user explicitly clicks a button
        setManualOverride(true)
        if (messageType === selectedType && data) return
        await fetchDataForType(messageType)
    }



    useEffect(() => {
        // Run once on mount
        updateTypeAndFetch()
    }, [])

    const selectedOption = MESSAGE_TYPES.find(t => t.value === selectedType)

    return (
        <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="flex items-center gap-2">
                    <span>📋</span>
                    <span>Ask Rides Reactions</span>
                </CardTitle>
                <div className="flex items-center gap-2">
                    <Button
                        variant="ghost"
                        size="sm"
                        onClick={updateTypeAndFetch}
                        title="Refresh data (resets to auto)"
                        className="h-8 w-8 p-0"
                        disabled={loading}
                    >
                        <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
                    </Button>
                    <InfoToggleButton
                        isOpen={showInfo}
                        onClick={() => setShowInfo(!showInfo)}
                        title="About Ask Rides Reactions"
                    />
                </div>
            </CardHeader>
            <CardContent>
                <InfoPanel
                    isOpen={showInfo}
                    onClose={() => setShowInfo(false)}
                    title="About Ask Rides Reactions"
                >
                    <div className="mb-3 p-3 bg-slate-50 dark:bg-zinc-800/50 rounded-lg border border-slate-200 dark:border-zinc-700">
                        <p className="text-sm font-medium text-slate-700 dark:text-slate-300">
                            Currently viewing: <strong>{selectedOption?.label}</strong> {!manualOverride && ['friday', 'sunday'].includes(selectedType) && <span className="text-slate-500 dark:text-slate-400">(Auto)</span>}
                        </p>
                        <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
                            {manualOverride ? 'Manual mode - click refresh to return to auto' : 'Automatic mode - switches based on current time'}
                        </p>
                    </div>
                    <p className="mb-2">
                        This widget shows detailed reactions from the ask rides announcements channel.
                    </p>
                    <ul className="list-disc list-inside space-y-1 text-sm text-slate-600 dark:text-slate-400">
                        <li>Automatically defaults to <strong>Friday</strong> or <strong>Sunday</strong> based on the time.</li>
                        <li>Select a message type using the buttons above.</li>
                        <li>Expand the list to see who reacted with each emoji.</li>
                        <li>Click on any username to copy it to your clipboard.</li>
                        <li>Click the refresh button to update data.</li>
                    </ul>
                </InfoPanel>

                <div className="mb-6 flex flex-wrap gap-2">
                    {MESSAGE_TYPES.map(type => (
                        <Button
                            key={type.value}
                            variant={selectedType === type.value ? 'default' : 'outline'}
                            onClick={() => handleTypeChange(type.value)}
                            disabled={loading}
                            className="flex-1 min-w-[120px]"
                        >
                            <span className="mr-2">{type.emoji}</span>
                            {type.label}
                            {selectedType === type.value && !manualOverride && ['friday', 'sunday'].includes(type.value) && (
                                <span className="ml-1 text-xs opacity-70">(Auto)</span>
                            )}
                        </Button>
                    ))}
                </div>

                {loading && <div className="text-center py-8 text-slate-500 animate-pulse">Loading reactions...</div>}

                {error && <ErrorMessage message={error} />}

                {!loading && !error && data && (
                    <div className="bg-white dark:bg-zinc-900 rounded-lg border border-slate-200 dark:border-zinc-800 overflow-hidden transition-all duration-300">
                        {!data.message_found ? (
                            <div className="text-center py-8 text-slate-500 italic">
                                No message found for {selectedOption?.label} this week.
                            </div>
                        ) : (
                            <div className="p-0">
                                <div className="p-4 bg-slate-50 dark:bg-zinc-800/50 border-b border-slate-100 dark:border-zinc-700/50 flex justify-between items-center">
                                    <h3 className="font-semibold text-slate-900 dark:text-slate-100">
                                        Reaction Breakdown
                                    </h3>
                                    <span className="text-xs font-medium text-slate-500 uppercase tracking-widest">
                                        {Object.values(data.reactions).reduce((acc, curr) => acc + curr.length, 0)} Total Reactions
                                    </span>
                                </div>

                                {Object.keys(data.reactions).length === 0 ? (
                                    <div className="text-center py-8 text-slate-500">No reactions found yet.</div>
                                ) : (
                                    <div className="p-4 space-y-6">
                                        {Object.entries(data.reactions).map(([emoji, usernames]) => (
                                            <div key={emoji}>
                                                <div className="flex items-center gap-2 mb-3">
                                                    <span className="text-2xl">{emoji}</span>
                                                    <span className="text-sm font-bold text-slate-600 dark:text-slate-400 uppercase tracking-wider">
                                                        {usernames.length} {usernames.length === 1 ? 'Person' : 'People'}
                                                    </span>
                                                </div>
                                                <div className="flex flex-wrap gap-2 pl-1">
                                                    {usernames.map((username) => (
                                                        <UsernamePill
                                                            key={username}
                                                            username={username}
                                                            displayName={data.username_to_name[username] || username}
                                                        />
                                                    ))}
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                )}
                            </div>
                        )}
                    </div>
                )}
            </CardContent>
        </Card>
    )
}

export default ReactionDetails
