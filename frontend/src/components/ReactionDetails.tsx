import { useState, useEffect } from 'react'
import { apiFetch } from '../lib/api'
import { useCopyToClipboard } from '../lib/utils'
import { Card, CardHeader, CardTitle, CardContent } from './ui/card'
import { Button } from './ui/button'
import { RefreshCw } from 'lucide-react'
import { InfoToggleButton, InfoPanel } from './InfoHelp'
import ErrorMessage from "./ErrorMessage"
import type { AskRidesReactionsData } from '../types'


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
    const [showInfo, setShowInfo] = useState(false)
    const { copyToClipboard } = useCopyToClipboard()
    const [copiedKey, setCopiedKey] = useState<string>('')

    const fetchDataForType = async (messageType: MessageType) => {
        setLoading(true)
        setError('')
        try {
            const response = await apiFetch(`/api/ask-rides/reactions/${messageType}`)
            if (!response.ok) {
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

    const handleTypeChange = async (messageType: MessageType) => {
        await fetchDataForType(messageType)
    }

    const handleRefresh = async () => {
        await fetchDataForType(selectedType)
    }

    useEffect(() => {
        fetchDataForType(selectedType)
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
                        onClick={handleRefresh}
                        title="Refresh data"
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
                            Currently viewing: <strong>{selectedOption?.label}</strong>
                        </p>
                    </div>
                    <p className="mb-2">
                        This widget shows detailed reactions from the ask rides announcements channel.
                    </p>
                    <ul className="list-disc list-inside space-y-1 text-sm text-slate-600 dark:text-slate-400">
                        <li>Use the dropdown to select which message type to view.</li>
                        <li>Expand the dropdown to see who reacted with each emoji.</li>
                        <li>Click on any username to copy it to your clipboard.</li>
                        <li>Click the refresh button to update data.</li>
                    </ul>
                </InfoPanel>

                <div className="mb-4">
                    <label htmlFor="message-type-select" className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                        Message Type
                    </label>
                    <select
                        id="message-type-select"
                        value={selectedType}
                        onChange={(e) => handleTypeChange(e.target.value as MessageType)}
                        disabled={loading}
                        className="w-full px-3 py-2 border border-slate-300 dark:border-zinc-700 rounded-md bg-white dark:bg-zinc-900 text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-blue-500 dark:focus:ring-blue-600 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                        {MESSAGE_TYPES.map(type => (
                            <option key={type.value} value={type.value}>
                                {type.emoji} {type.label}
                            </option>
                        ))}
                    </select>
                </div>

                {loading && <div className="text-center py-4 text-slate-500">Loading reactions...</div>}

                {error && <ErrorMessage message={error} />}

                {!loading && !error && data && (
                    <>
                        {!data.message_found ? (
                            <div className="text-center py-4 text-slate-500 italic">
                                No message found for {selectedOption?.label}.
                            </div>
                        ) : (
                            <div className="space-y-4">
                                {Object.keys(data.reactions).length === 0 ? (
                                    <div className="text-center py-4 text-slate-500">No reactions found yet.</div>
                                ) : (
                                    <details className="group border border-slate-200 dark:border-zinc-700 rounded-lg bg-white dark:bg-zinc-900 overflow-hidden">
                                        <summary className="flex items-center justify-between p-4 cursor-pointer hover:bg-slate-50 dark:hover:bg-zinc-800/50 transition-colors select-none list-none [&::-webkit-details-marker]:hidden">
                                            <div className="flex flex-wrap items-center gap-x-6 gap-y-2">
                                                {Object.entries(data.reactions).map(([emoji, usernames]) => (
                                                    <div key={emoji} className="flex items-center gap-2">
                                                        <span className="text-xl">{emoji}</span>
                                                        <span className="text-sm font-medium text-slate-700 dark:text-slate-300">
                                                            {usernames.length}
                                                        </span>
                                                    </div>
                                                ))}
                                            </div>
                                            <span className="text-slate-400 group-open:rotate-180 transition-transform duration-200 ml-4">
                                                ▼
                                            </span>
                                        </summary>
                                        <div className="px-4 pb-4 pt-0 border-t border-slate-100 dark:border-zinc-800/50">
                                            <div className="space-y-4 mt-4">
                                                {Object.entries(data.reactions).map(([emoji, usernames]) => (
                                                    <div key={emoji}>
                                                        <div className="flex items-center gap-2 mb-2">
                                                            <span className="text-lg">{emoji}</span>
                                                            <span className="text-sm font-medium text-slate-500 uppercase tracking-widest text-xs">
                                                                {usernames.length} {usernames.length === 1 ? 'Person' : 'People'}
                                                            </span>
                                                        </div>
                                                        <div className="flex flex-wrap gap-2">
                                                            {usernames.map((username) => {
                                                                const compositeKey = `${emoji}-${username}`
                                                                const displayName = data.username_to_name[username] || username
                                                                return (
                                                                    <span
                                                                        key={username}
                                                                        onClick={() => {
                                                                            copyToClipboard("@" + username)
                                                                            setCopiedKey(compositeKey)
                                                                            setTimeout(() => {
                                                                                setCopiedKey('')
                                                                            }, 5000)
                                                                        }}
                                                                        className={`px-2 py-1 rounded text-sm cursor-pointer transition-all duration-300 border ${copiedKey === compositeKey
                                                                            ? 'bg-green-100 dark:bg-green-900/30 text-green-800 dark:text-green-300 border-green-300 dark:border-green-700'
                                                                            : 'bg-slate-100 dark:bg-zinc-800 text-slate-700 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-zinc-700 border-transparent'
                                                                            }`}
                                                                        title={copiedKey === compositeKey ? '✓ Copied!' : 'Click to copy username'}
                                                                    >
                                                                        {copiedKey === compositeKey && '✓ '}
                                                                        {displayName}
                                                                    </span>
                                                                )
                                                            })}
                                                        </div>
                                                    </div>
                                                ))}
                                            </div>
                                        </div>
                                    </details>
                                )}
                            </div>
                        )}
                    </>
                )}
            </CardContent>
        </Card>
    )
}

export default ReactionDetails
