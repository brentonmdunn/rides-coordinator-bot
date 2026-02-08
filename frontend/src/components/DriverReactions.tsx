import { useState, useEffect } from 'react'
import { apiFetch } from '../lib/api'
import { useCopyToClipboard } from '../lib/utils'
import { Card, CardHeader, CardTitle, CardContent } from './ui/card'
import { Button } from './ui/button'
import { RefreshCw } from 'lucide-react'
import { InfoToggleButton, InfoPanel } from './InfoHelp'
import ErrorMessage from "./ErrorMessage"


interface DriverReactionsData {
    day: string
    reactions: Record<string, string[]>
    username_to_name: Record<string, string>
    message_found: boolean
}

function DriverReactions() {
    const [data, setData] = useState<DriverReactionsData | null>(null)
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState('')
    const [activeDay, setActiveDay] = useState<'Friday' | 'Sunday'>('Friday')
    const [manualOverride, setManualOverride] = useState(false)
    const [showInfo, setShowInfo] = useState(false)
    const { copyToClipboard } = useCopyToClipboard()
    const [copiedKey, setCopiedKey] = useState<string>('')

    const getAutomaticDay = (): 'Friday' | 'Sunday' => {
        const now = new Date()
        const day = now.getDay()
        const hour = now.getHours()

        if (day === 6 || day === 0) {
            // Saturday or Sunday
            return 'Sunday'
        } else if (day === 5 && hour >= 22) {
            // Friday after 10pm
            return 'Sunday'
        } else {
            // Mon, Tue, Wed, Thu, Fri (before 10pm)
            return 'Friday'
        }
    }

    const fetchDataForDay = async (day: 'Friday' | 'Sunday') => {
        setLoading(true)
        setError('')
        try {
            const response = await apiFetch(`/api/check-pickups/driver-reactions/${day.toLowerCase()}`)
            if (!response.ok) {
                throw new Error('Failed to fetch driver reactions')
            }
            const result = await response.json()
            setData(result)
            setActiveDay(day)
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Unknown error')
        } finally {
            setLoading(false)
        }
    }

    const updateDayAndFetch = async () => {
        const currentDay = getAutomaticDay()
        setManualOverride(false)
        await fetchDataForDay(currentDay)
    }

    const handleDayToggle = async (day: 'Friday' | 'Sunday') => {
        // Set state immediately for instant visual feedback
        setManualOverride(true)
        setActiveDay(day)
        await fetchDataForDay(day)
    }

    useEffect(() => {
        updateDayAndFetch()
    }, [])

    return (
        <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="flex items-center gap-2">
                    <span>🚙</span>
                    <span>Driver Reactions ({activeDay})</span>
                </CardTitle>
                <div className="flex items-center gap-2">
                    <Button
                        variant="ghost"
                        size="sm"
                        onClick={updateDayAndFetch}
                        title="Refresh data"
                        className="h-8 w-8 p-0"
                        disabled={loading}
                    >
                        <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
                    </Button>
                    <InfoToggleButton
                        isOpen={showInfo}
                        onClick={() => setShowInfo(!showInfo)}
                        title="About Driver Reactions"
                    />
                </div>
            </CardHeader>
            <CardContent>
                <InfoPanel
                    isOpen={showInfo}
                    onClose={() => setShowInfo(false)}
                    title="About Driver Reactions"
                >
                    <div className="mb-3 p-3 bg-slate-50 dark:bg-zinc-800/50 rounded-lg border border-slate-200 dark:border-zinc-700">
                        <p className="text-sm font-medium text-slate-700 dark:text-slate-300">
                            Currently viewing: <strong>{activeDay}</strong> {!manualOverride && <span className="text-slate-500 dark:text-slate-400">(Auto)</span>}
                        </p>
                        <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
                            {manualOverride ? 'Manual mode - click refresh to return to auto' : 'Automatic mode - switches based on current time'}
                        </p>
                    </div>
                    <p className="mb-2">
                        This widget tracks emoji reactions from drivers in the driver chat channel.
                    </p>
                    <ul className="list-disc list-inside space-y-1 text-sm text-slate-600 dark:text-slate-400">
                        <li>Automatically switches between <strong>Friday</strong> and <strong>Sunday</strong> based on the current time.</li>
                        <li>Use the day toggle buttons to manually switch between Friday and Sunday views.</li>
                        <li>Click the refresh button to return to automatic mode and update data.</li>
                        <li>Expand the dropdown to see who reacted with each emoji.</li>
                        <li>Click on any driver's username to copy it to your clipboard.</li>
                    </ul>
                </InfoPanel>

                <div className="mb-4 flex gap-2">
                    <Button
                        variant={activeDay === 'Friday' ? 'default' : 'outline'}
                        size="sm"
                        onClick={() => handleDayToggle('Friday')}
                        disabled={loading}
                        className="flex-1"
                    >
                        Friday {activeDay === 'Friday' && !manualOverride && '(Auto)'}
                    </Button>
                    <Button
                        variant={activeDay === 'Sunday' ? 'default' : 'outline'}
                        size="sm"
                        onClick={() => handleDayToggle('Sunday')}
                        disabled={loading}
                        className="flex-1"
                    >
                        Sunday {activeDay === 'Sunday' && !manualOverride && '(Auto)'}
                    </Button>
                </div>

                {loading && <div className="text-center py-4 text-slate-500">Loading reactions...</div>}

                {error && <ErrorMessage message={error} />}

                {!loading && !error && data && (
                    <>
                        {!data.message_found ? (
                            <div className="text-center py-4 text-slate-500 italic">
                                No driver message found for {activeDay}.
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
                                                                {usernames.length} {usernames.length === 1 ? 'Driver' : 'Drivers'}
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

export default DriverReactions
