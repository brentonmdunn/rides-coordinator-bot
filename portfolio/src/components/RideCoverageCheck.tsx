import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiFetch } from '../lib/api'
import ErrorMessage from "./ErrorMessage"
import type { RideCoverage, RideCoverageUser } from '../types'
import { InfoToggleButton, InfoPanel } from './InfoHelp'
import { Button } from './ui/button'
import { RefreshCw, MoreVertical, CloudDownload, Check } from 'lucide-react'
import { getAutomaticDay } from '../lib/utils'
import { QUERY_STALE_5_MIN, COVERAGE_PERCENTAGE_MULTIPLIER } from '../lib/constants'
import { CoverageSkeleton } from './LoadingSkeleton'
import { RefreshIconButton, SectionCard } from './shared'

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
            return response.json()
        },
        // Cache data for 5 minutes to prevent excessive Discord API calls
        staleTime: QUERY_STALE_5_MIN,
        // Disable aggressive refetching to avoid rate limits
        refetchOnWindowFocus: false,
        refetchOnMount: false,
    })

    if (isLoading) {
        return <CoverageSkeleton />
    }

    if (error) {
        return <ErrorMessage message={`Failed to load ${title.toLowerCase()} coverage`} />
    }

    if (!coverage || !coverage.message_found) {
        return (
            <div className="p-4 text-center text-muted-foreground">
                No {title.toLowerCase()} message found yet
            </div>
        )
    }

    const percentAssigned = coverage.total > 0
        ? Math.round((coverage.assigned / coverage.total) * COVERAGE_PERCENTAGE_MULTIPLIER)
        : 0

    return (
        <div className="border border-border rounded-lg overflow-hidden">
            <button
                onClick={() => setIsExpanded(!isExpanded)}
                className="w-full px-4 py-3 flex items-center justify-between bg-muted hover:bg-muted/70 transition-colors"
            >
                <div className="flex items-center gap-3">
                    <span className="text-2xl">{emoji}</span>
                    <div className="text-left">
                        <h3 className="font-semibold text-foreground">{title}</h3>
                        <p className="text-sm text-muted-foreground">
                            {coverage.assigned} / {coverage.total} assigned ({percentAssigned}%)
                        </p>
                    </div>
                </div>
                <div className="flex items-center gap-2">
                    {coverage.assigned === coverage.total ? (
                        <span className="text-success-text font-medium">✓ Complete</span>
                    ) : (
                        <span className="text-yellow-600 dark:text-yellow-400 font-medium">
                            {coverage.total - coverage.assigned} missing
                        </span>
                    )}
                    <svg
                        className={`w-5 h-5 text-muted-foreground transition-transform ${isExpanded ? 'rotate-180' : ''}`}
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                    >
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                    </svg>
                </div>
            </button>

            {isExpanded && (
                <div className="p-4 bg-card">
                    {coverage.users.length === 0 ? (
                        <p className="text-center text-muted-foreground">No users reacted to this message</p>
                    ) : (
                        <div className="space-y-2">
                            {coverage.users.map((user: RideCoverageUser) => (
                                <div
                                    key={user.discord_username}
                                    className="flex items-center justify-between px-3 py-2 rounded-md bg-muted"
                                >
                                    <span className="font-mono text-sm text-foreground">
                                        {user.discord_username}
                                    </span>
                                    {user.has_ride ? (
                                        <span className="text-success-text font-bold text-lg">✓</span>
                                    ) : (
                                        <span className="text-destructive-text font-bold text-lg">✗</span>
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

    const currentRideType = getAutomaticDay()

    // Check if a message exists for the current ride type
    const {
        data: messageCheck,
        isLoading: isCheckingMessage
    } = useQuery<RideCoverage>({
        queryKey: ['rideCoverage', currentRideType],
        queryFn: async () => {
            const response = await apiFetch(`/api/check-pickups/${currentRideType}`)
            return response.json()
        },
        staleTime: QUERY_STALE_5_MIN,
        refetchOnWindowFocus: false,
        refetchOnMount: false,
    })

    const syncMutation = useMutation({
        mutationFn: async () => {
            const response = await apiFetch('/api/check-pickups/sync', {
                method: 'POST'
            })
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

    if (!messageCheck || !messageCheck.is_in_visibility_window) {
        return null // Hide widget outside the coverage visibility window
    }

    return (
        <SectionCard
            cardClassName="!overflow-visible"
            headerClassName="!overflow-visible"
            icon={undefined}
            title="Ride Coverage Check"
            actions={
                <>
                    <RefreshIconButton onClick={handleRefresh} />
                    <div className="relative">
                        <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => setShowMenu(!showMenu)}
                            title="More options"
                            aria-label="More options"
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
                                <div className="absolute right-0 top-full mt-1 z-20 bg-popover border border-border rounded-md shadow-xl py-1 w-48">
                                    <button
                                        onClick={() => syncMutation.mutate()}
                                        disabled={syncMutation.isPending}
                                        className="w-full px-3 py-2 text-left text-sm flex items-center gap-2 hover:bg-muted transition-colors disabled:opacity-50 disabled:cursor-not-allowed text-foreground"
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
                </>
            }
        >
                {syncMutation.isSuccess && (
                    <div className="mb-4 p-3 bg-success/10 text-success-text rounded-md text-sm flex items-center gap-2">
                        <Check className="h-4 w-4" />
                        <span>
                            Sync completed: {syncMutation.data?.entries_added || 0} added, {syncMutation.data?.entries_removed || 0} removed
                        </span>
                    </div>
                )}
                {syncMutation.isError && (
                    <div className="mb-4 p-3 bg-destructive/10 text-destructive-text rounded-md text-sm">
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
                            <span className="text-success-text font-bold">✓</span>
                            <span>User is covered (assigned to a driver)</span>
                        </li>
                        <li className="flex items-center gap-2">
                            <span className="text-destructive-text font-bold">✗</span>
                            <span>User not covered (needs a ride!)</span>
                        </li>
                    </ul>

                    <div className="space-y-3">
                        <div className="border-t border-border pt-2">
                            <p className="text-sm text-muted-foreground">
                                This widget only appears once the first ride grouping message is posted in Discord.
                            </p>
                        </div>

                        <div className="border-t border-border pt-2">
                            <p className="text-sm font-medium text-foreground mb-1">Tools</p>
                            <ul className="text-sm text-muted-foreground space-y-1">
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
                    {currentRideType === 'sunday' ? (
                        <RideDay rideType="sunday" title="Weekly Event 2" emoji="" />
                    ) : (
                        <RideDay rideType="friday" title="Weekly Event 1" emoji="" />
                    )}
                </div>
        </SectionCard>
    )
}

export default RideCoverageCheck
