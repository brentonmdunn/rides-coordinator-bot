import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiFetch } from '../lib/api'
import ErrorMessage from "./ErrorMessage"
import type { RideCoverage, RideCoverageUser } from '../types'
import { InfoToggleButton, InfoPanel } from './InfoHelp'
import { Card, CardHeader, CardTitle, CardContent } from './ui/card'
import { Button } from './ui/button'
import { RefreshCw, MoreVertical, CloudDownload, Check } from 'lucide-react'

interface RideDayProps {
    rideType: 'friday' | 'sunday'
    title: string
    emoji: string
}

function RideDay({ rideType, title, emoji }: RideDayProps) {
    const [isExpanded, setIsExpanded] = useState(false)

    const {
        data: coverage,
        isLoading,
        error
    } = useQuery<RideCoverage>({
        queryKey: ['rideCoverage', rideType],
        queryFn: async () => {
            const response = await apiFetch(`/api/check-pickups/${rideType}`)
            if (!response.ok) {
                throw new Error('Failed to load ride coverage')
            }
            return response.json()
        },
        // Cache data for 5 minutes to prevent excessive Discord API calls
        staleTime: 5 * 60 * 1000,
        // Disable aggressive refetching to avoid rate limits
        refetchOnWindowFocus: false,
        refetchOnMount: false,
        refetchOnReconnect: false,
    })

    if (isLoading) {
        return (
            <div className="p-4 text-center text-slate-500 animate-pulse">
                Loading {title.toLowerCase()} coverage...
            </div>
        )
    }

    if (error) {
        return <ErrorMessage message={`Failed to load ${title.toLowerCase()} coverage`} />
    }

    if (!coverage || !coverage.message_found) {
        return (
            <div className="p-4 text-center text-slate-500">
                No {title.toLowerCase()} message found yet
            </div>
        )
    }

    const percentAssigned = coverage.total > 0
        ? Math.round((coverage.assigned / coverage.total) * 100)
        : 0

    return (
        <div className="border border-slate-200 dark:border-slate-700 rounded-lg overflow-hidden">
            <button
                onClick={() => setIsExpanded(!isExpanded)}
                className="w-full px-4 py-3 flex items-center justify-between bg-slate-50 dark:bg-slate-800 hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors"
            >
                <div className="flex items-center gap-3">
                    <span className="text-2xl">{emoji}</span>
                    <div className="text-left">
                        <h3 className="font-semibold text-slate-900 dark:text-white">{title}</h3>
                        <p className="text-sm text-slate-600 dark:text-slate-400">
                            {coverage.assigned} / {coverage.total} assigned ({percentAssigned}%)
                        </p>
                    </div>
                </div>
                <div className="flex items-center gap-2">
                    {coverage.assigned === coverage.total ? (
                        <span className="text-green-600 dark:text-green-400 font-medium">✓ Complete</span>
                    ) : (
                        <span className="text-yellow-600 dark:text-yellow-400 font-medium">
                            {coverage.total - coverage.assigned} missing
                        </span>
                    )}
                    <svg
                        className={`w-5 h-5 text-slate-400 transition-transform ${isExpanded ? 'rotate-180' : ''}`}
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                    >
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                    </svg>
                </div>
            </button>

            {isExpanded && (
                <div className="p-4 bg-white dark:bg-slate-900">
                    {coverage.users.length === 0 ? (
                        <p className="text-center text-slate-500">No users reacted to this message</p>
                    ) : (
                        <div className="space-y-2">
                            {coverage.users.map((user: RideCoverageUser) => (
                                <div
                                    key={user.discord_username}
                                    className="flex items-center justify-between px-3 py-2 rounded-md bg-slate-50 dark:bg-slate-800"
                                >
                                    <span className="font-mono text-sm text-slate-900 dark:text-slate-100">
                                        {user.discord_username}
                                    </span>
                                    {user.has_ride ? (
                                        <span className="text-green-600 dark:text-green-400 font-bold text-lg">✓</span>
                                    ) : (
                                        <span className="text-red-600 dark:text-red-400 font-bold text-lg">✗</span>
                                    )}
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            )}
        </div>
    )
}

function RideCoverageCheck() {
    const [showInfo, setShowInfo] = useState(false)
    const [showMenu, setShowMenu] = useState(false)
    const queryClient = useQueryClient()

    // Determine which ride type to check based on current time
    const now = new Date()
    const day = now.getDay()
    const hour = now.getHours()

    // Show Sunday coverage if:
    // - Friday after 10pm (22:00)
    // - Saturday (all day)
    // - Sunday (all day)
    const showSunday = (day === 5 && hour >= 22) || day === 6 || day === 0
    const currentRideType = showSunday ? 'sunday' : 'friday'

    // Check if a message exists for the current ride type
    const {
        data: messageCheck,
        isLoading: isCheckingMessage
    } = useQuery<RideCoverage>({
        queryKey: ['rideCoverage', currentRideType],
        queryFn: async () => {
            const response = await apiFetch(`/api/check-pickups/${currentRideType}`)
            if (!response.ok) {
                throw new Error('Failed to check message')
            }
            return response.json()
        },
        staleTime: 5 * 60 * 1000,
        refetchOnWindowFocus: false,
        refetchOnMount: false,
        refetchOnReconnect: false,
    })

    const syncMutation = useMutation({
        mutationFn: async () => {
            const response = await apiFetch('/api/check-pickups/sync', {
                method: 'POST'
            })
            if (!response.ok) {
                throw new Error('Failed to sync ride coverage')
            }
            return response.json()
        },
        onSuccess: () => {
            // Invalidate and refetch ride coverage data
            queryClient.invalidateQueries({ queryKey: ['rideCoverage'] })
            setShowMenu(false)
        }
    })

    const handleRefresh = () => {
        queryClient.invalidateQueries({ queryKey: ['rideCoverage'] })
    }

    // Hide the widget if we're still checking or if no coverage entries exist
    if (isCheckingMessage) {
        return null // Don't show anything while checking
    }

    if (!messageCheck || !messageCheck.has_coverage_entries) {
        return null // Hide widget when no drive messages have been posted yet
    }

    return (
        <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle><span>🎯</span> Ride Coverage Check</CardTitle>
                <div className="flex items-center gap-2">
                    <Button
                        variant="ghost"
                        size="sm"
                        onClick={handleRefresh}
                        title="Refresh data"
                        className="h-8 w-8 p-0"
                    >
                        <RefreshCw className="h-4 w-4" />
                    </Button>
                    <div className="relative">
                        <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => setShowMenu(!showMenu)}
                            title="More options"
                            className="h-8 w-8 p-0"
                        >
                            <MoreVertical className="h-4 w-4" />
                        </Button>
                        {showMenu && (
                            <>
                                <div
                                    className="fixed inset-0 z-10"
                                    onClick={() => setShowMenu(false)}
                                />
                                <div className="absolute right-0 top-full mt-1 z-20 bg-white dark:bg-slate-950 border border-slate-200 dark:border-slate-800 rounded-md shadow-lg py-1 min-w-0 w-full max-w-xs">
                                    <button
                                        onClick={() => syncMutation.mutate()}
                                        disabled={syncMutation.isPending}
                                        className="w-full px-3 py-2 text-left text-sm flex items-center gap-2 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors disabled:opacity-50 disabled:cursor-not-allowed text-slate-700 dark:text-slate-300"
                                    >
                                        {syncMutation.isPending ? (
                                            <>
                                                <RefreshCw className="h-4 w-4 animate-spin" />
                                                <span>Syncing...</span>
                                            </>
                                        ) : (
                                            <>
                                                <CloudDownload className="h-4 w-4" />
                                                <span>Force Sync from Discord</span>
                                            </>
                                        )}
                                    </button>
                                </div>
                            </>
                        )}
                    </div>
                    <InfoToggleButton
                        isOpen={showInfo}
                        onClick={() => setShowInfo(!showInfo)}
                        title="About Ride Coverage"
                    />
                </div>
            </CardHeader>
            <CardContent>
                {syncMutation.isSuccess && (
                    <div className="mb-4 p-3 bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-400 rounded-md text-sm flex items-center gap-2">
                        <Check className="h-4 w-4" />
                        <span>
                            Sync completed: {syncMutation.data?.entries_added || 0} added, {syncMutation.data?.entries_removed || 0} removed
                        </span>
                    </div>
                )}
                {syncMutation.isError && (
                    <div className="mb-4 p-3 bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-400 rounded-md text-sm">
                        ✗ Sync failed. Please try again.
                    </div>
                )}

                <InfoPanel
                    isOpen={showInfo}
                    onClose={() => setShowInfo(false)}
                    title="About Ride Coverage"
                >
                    <p className="mb-2">
                        This dashboard tracks which users who reacted to ride posts have been assigned to a driver.
                    </p>
                    <ul className="space-y-1 mb-3">
                        <li className="flex items-center gap-2">
                            <span className="text-green-600 dark:text-green-400 font-bold">✓</span>
                            <span>User is covered (assigned to a driver)</span>
                        </li>
                        <li className="flex items-center gap-2">
                            <span className="text-red-600 dark:text-red-400 font-bold">✗</span>
                            <span>User not covered (needs a ride!)</span>
                        </li>
                    </ul>

                    <div className="space-y-3">
                        <div className="border-t border-slate-100 dark:border-slate-800 pt-2">
                            <p className="text-sm text-slate-600 dark:text-slate-400">
                                This widget only appears once the first ride grouping message is posted in Discord.
                            </p>
                        </div>

                        <div className="border-t border-slate-100 dark:border-slate-800 pt-2">
                            <p className="text-sm font-medium text-slate-900 dark:text-slate-100 mb-1">Tools</p>
                            <ul className="text-sm text-slate-600 dark:text-slate-400 space-y-1">
                                <li className="flex items-center gap-2">
                                    <RefreshCw className="h-3 w-3" />
                                    <span><strong>Refresh:</strong> Reloads data from database</span>
                                </li>
                                <li className="flex items-center gap-2">
                                    <CloudDownload className="h-3 w-3" />
                                    <span><strong>Force Sync:</strong> Rescans Discord messages (use if data seems out of sync)</span>
                                </li>
                            </ul>
                        </div>
                    </div>
                </InfoPanel>

                <div className="space-y-4">
                    {showSunday ? (
                        <RideDay rideType="sunday" title="Sunday Service" emoji="⛪" />
                    ) : (
                        <RideDay rideType="friday" title="Friday Fellowship" emoji="🎉" />
                    )}
                </div>
            </CardContent>
        </Card>
    )
}

export default RideCoverageCheck
