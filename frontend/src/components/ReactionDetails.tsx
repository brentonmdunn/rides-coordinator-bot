import { useState, useEffect, useCallback } from 'react'
import { Sparkles, Church, BookOpen, ClipboardList, ChevronDown } from 'lucide-react'
import type React from 'react'
import { getAutomaticDay } from '../lib/utils'
import { apiFetch, ApiError } from '../lib/api'
import { Button } from './ui/button'
import { InfoToggleButton, InfoPanel } from './InfoHelp'
import ErrorMessage from "./ErrorMessage"
import { ListSkeleton } from './LoadingSkeleton'
import type { AskRidesReactionsData } from '../types'
import { CopyPill } from './CopyPill'
import { RefreshIconButton, SectionCard } from './shared'


type MessageType = 'friday' | 'sunday' | 'sunday_class'

interface MessageTypeOption {
    value: MessageType
    label: string
    icon: React.ReactNode
}

const MESSAGE_TYPES: MessageTypeOption[] = [
    { value: 'friday', label: 'Friday Fellowship', icon: <Sparkles className="h-4 w-4" /> },
    { value: 'sunday', label: 'Sunday Service', icon: <Church className="h-4 w-4" /> },
    { value: 'sunday_class', label: 'Sunday Class', icon: <BookOpen className="h-4 w-4" /> },
]

/** Human-readable labels for ride-reaction emojis, shown in the overview. */
const EMOJI_LABELS: Record<string, string> = {
    '🍔': 'Lunch',
    '🏠': 'No lunch',
    '✳️': 'Something else',
    '🪨': 'Friday Fellowship',
    '📖': 'Sunday class',
    '➡️': 'Drive there',
    '⬅️': 'Drive back',
    '✅': 'Confirmed',
}

function ReactionDetails() {
    const [data, setData] = useState<AskRidesReactionsData | null>(null)
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState('')
    const [selectedType, setSelectedType] = useState<MessageType>('friday')

    const [showInfo, setShowInfo] = useState(false)
    const [showDetail, setShowDetail] = useState(false)



    const fetchDataForType = async (messageType: MessageType) => {
        setLoading(true)
        setError('')
        try {
            const response = await apiFetch(`/api/ask-rides/reactions/${messageType}`)
            const result = await response.json()
            setData(result)
            setSelectedType(messageType)
        } catch (err) {
            if (err instanceof ApiError && err.status === 404) {
                setData({
                    message_type: messageType,
                    reactions: {},
                    username_to_name: {},
                    message_found: false
                })
                setSelectedType(messageType)
                return
            }
            setError(err instanceof Error ? err.message : 'Unknown error')
        } finally {
            setLoading(false)
        }
    }

    const updateTypeAndFetch = useCallback(async () => {
        const currentType = getAutomaticDay()
        await fetchDataForType(currentType)
    }, [])

    const handleTypeChange = async (messageType: MessageType) => {
        if (messageType === selectedType && data) return
        await fetchDataForType(messageType)
    }



    useEffect(() => {
        // Run once on mount
        updateTypeAndFetch()
    }, [updateTypeAndFetch])

    const selectedOption = MESSAGE_TYPES.find(t => t.value === selectedType)

    // Build the combined overview: Discord reactions + tagged non-Discord riders.
    const reactions = data?.reactions ?? {}
    const nonDiscord = data?.non_discord ?? {}
    const overviewRows = Array.from(
        new Set([...Object.keys(reactions), ...Object.keys(nonDiscord)])
    )
        .map((emoji) => {
            const reacted = reactions[emoji]?.length ?? 0
            const added = nonDiscord[emoji]?.length ?? 0
            return { emoji, reacted, added, total: reacted + added }
        })
        .sort((a, b) => b.total - a.total)
    const uniqueReacted = new Set(Object.values(reactions).flat()).size
    const totalAdded = Object.values(nonDiscord).reduce((sum, names) => sum + names.length, 0)

    return (
        <SectionCard
            icon={<ClipboardList className="h-4 w-4" />}
            title="Ask Rides Overview"
            actions={
                <>
                    <RefreshIconButton
                        onClick={updateTypeAndFetch}
                        isLoading={loading}
                        title="Refresh data (resets to auto)"
                    />
                    <InfoToggleButton
                        isOpen={showInfo}
                        onClick={() => setShowInfo(!showInfo)}
                        title="About Ask Rides Overview"
                    />
                </>
            }
        >
                <InfoPanel
                    isOpen={showInfo}
                    onClose={() => setShowInfo(false)}
                    title="About Ask Rides Overview"
                >
                    <div className="mb-3 p-3 bg-muted/50 rounded-lg border border-border">
                        <p className="text-sm font-medium text-foreground">
                            Currently viewing: <strong>{selectedOption?.label}</strong>
                        </p>
                        <p className="text-xs text-muted-foreground mt-1">
                            Automatically switches based on current time. Click refresh to reset.
                        </p>
                    </div>
                    <p className="mb-2">
                        A per-reaction overview for the ask rides announcement, combining Discord
                        reactions with manually-added non-Discord riders.
                    </p>
                    <ul className="list-disc list-inside space-y-1 text-sm text-muted-foreground">
                        <li>Each row shows the total for a reaction, split as <strong>reacted + added</strong> when manual entries exist.</li>
                        <li><strong>Reacted</strong> counts always match the Discord post exactly; <strong>added</strong> comes from the Non-Discord Rides widget.</li>
                        <li>Automatically defaults to <strong>Friday</strong> or <strong>Sunday</strong> based on the time.</li>
                        <li>Expand <strong>Who reacted</strong> to see names; click a name to copy it.</li>
                    </ul>
                </InfoPanel>

                <div className="mb-6 flex flex-col md:flex-row gap-2">
                    {MESSAGE_TYPES.map(type => (
                        <Button
                            key={type.value}
                            variant={selectedType === type.value ? 'default' : 'outline'}
                            onClick={() => handleTypeChange(type.value)}
                            disabled={loading}
                            className="flex-1 min-w-[120px] w-full md:w-auto"
                        >
                            {type.icon}
                            {type.label}

                        </Button>
                    ))}
                </div>

                {loading && <ListSkeleton rows={5} />}

                {error && <ErrorMessage message={error} />}

                {!loading && !error && data && (
                    <div className="bg-card rounded-lg border border-border overflow-hidden transition-all duration-300">
                        {!data.message_found && overviewRows.length === 0 ? (
                            <div className="text-center py-8 text-muted-foreground italic">
                                No message found for {selectedOption?.label} this week.
                            </div>
                        ) : (
                            <div className="p-0">
                                {/* Overview header */}
                                <div className="p-4 bg-muted/50 border-b border-border flex justify-between items-center">
                                    <h3 className="font-semibold text-foreground">Overview</h3>
                                    <span className="text-xs font-medium text-muted-foreground uppercase tracking-widest">
                                        {uniqueReacted} reacted{totalAdded > 0 ? ` + ${totalAdded} added` : ''}
                                    </span>
                                </div>

                                {!data.message_found && (
                                    <div className="px-4 pt-3 text-xs text-muted-foreground italic">
                                        No Discord message found yet — showing manually added riders only.
                                    </div>
                                )}

                                {/* Category overview */}
                                {overviewRows.length === 0 ? (
                                    <div className="text-center py-8 text-muted-foreground">No reactions yet.</div>
                                ) : (
                                    <div className="p-4 space-y-2">
                                        {overviewRows.map((row) => (
                                            <div
                                                key={row.emoji}
                                                className="flex items-center justify-between px-3 py-2 rounded-md bg-muted"
                                            >
                                                <div className="flex items-center gap-2 min-w-0">
                                                    <span className="text-xl">{row.emoji}</span>
                                                    <span className="text-sm font-medium text-foreground">
                                                        {EMOJI_LABELS[row.emoji] ?? row.emoji}
                                                    </span>
                                                </div>
                                                <div className="text-sm text-foreground whitespace-nowrap">
                                                    <span className="font-semibold">{row.total}</span>
                                                    {row.added > 0 && (
                                                        <span className="text-muted-foreground">
                                                            {' '}({row.reacted} reacted + {row.added} added)
                                                        </span>
                                                    )}
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                )}

                                {/* Collapsible: who reacted (Discord + non-Discord) */}
                                {(Object.keys(reactions).length > 0 || Object.keys(nonDiscord).length > 0) && (
                                    <div className="border-t border-border">
                                        <button
                                            type="button"
                                            onClick={() => setShowDetail(v => !v)}
                                            className="w-full px-4 py-3 flex items-center justify-between text-sm font-medium text-foreground hover:bg-muted/50 transition-colors"
                                        >
                                            <span>Who reacted</span>
                                            <ChevronDown
                                                className={`h-4 w-4 transition-transform ${showDetail ? 'rotate-180' : ''}`}
                                            />
                                        </button>
                                        {showDetail && (
                                            <div className="p-4 space-y-6">
                                                {Array.from(
                                                    new Set([...Object.keys(reactions), ...Object.keys(nonDiscord)])
                                                ).map((emoji) => {
                                                    const discordUsers = reactions[emoji] ?? []
                                                    const nonDiscordNames = nonDiscord[emoji] ?? []
                                                    const total = discordUsers.length + nonDiscordNames.length
                                                    return (
                                                        <div key={emoji}>
                                                            <div className="flex items-center gap-2 mb-3">
                                                                <span className="text-2xl">{emoji}</span>
                                                                <span className="text-sm font-bold text-muted-foreground uppercase tracking-wider">
                                                                    {total} {total === 1 ? 'Person' : 'People'}
                                                                </span>
                                                            </div>
                                                            <div className="flex flex-wrap gap-2 pl-1">
                                                                {discordUsers.map((username) => (
                                                                    <CopyPill
                                                                        key={username}
                                                                        copyStr={"@" + username}
                                                                        displayStr={data.username_to_name[username] || ("@" + username)}
                                                                    />
                                                                ))}
                                                                {nonDiscordNames.map((name) => (
                                                                    <CopyPill
                                                                        key={`nd-${name}`}
                                                                        copyStr={name}
                                                                        displayStr={name}
                                                                        variant="muted"
                                                                    />
                                                                ))}
                                                            </div>
                                                        </div>
                                                    )
                                                })}
                                            </div>
                                        )}
                                    </div>
                                )}
                            </div>
                        )}
                    </div>
                )}
        </SectionCard>
    )
}

export default ReactionDetails
