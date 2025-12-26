import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '../lib/api'
import ErrorMessage from "./ErrorMessage"
import type { RideCoverage, RideCoverageUser } from '../types'
import { InfoToggleButton, InfoPanel } from './InfoHelp'
import { Card, CardHeader, CardTitle, CardContent } from './ui/card'

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

    const now = new Date()
    const day = now.getDay()
    const hour = now.getHours()

    // Show Sunday coverage if:
    // - Friday after 10pm (22:00)
    // - Saturday (all day)
    // - Sunday (all day)
    const showSunday = (day === 5 && hour >= 22) || day === 6 || day === 0

    return (
        <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle><span>🎯</span> Ride Coverage Check</CardTitle>
                <InfoToggleButton
                    isOpen={showInfo}
                    onClick={() => setShowInfo(!showInfo)}
                    title="About Ride Coverage"
                />
            </CardHeader>
            <CardContent>
                <InfoPanel
                    isOpen={showInfo}
                    onClose={() => setShowInfo(false)}
                    title="About Ride Coverage"
                >
                    <p className="mb-2">
                        This dashboard shows which users who reacted to ride request messages have been assigned to ride groups.
                    </p>
                    <ul className="space-y-1">
                        <li className="flex items-center gap-2">
                            <span className="text-green-600 dark:text-green-400 font-bold">✓</span>
                            <span>User has a ride assignment (location found in database)</span>
                        </li>
                        <li className="flex items-center gap-2">
                            <span className="text-red-600 dark:text-red-400 font-bold">✗</span>
                            <span>User does not have a ride assignment (needs attention!)</span>
                        </li>
                    </ul>
                    <div className="mt-3 border-t border-slate-100 dark:border-slate-800 pt-2">
                        <p className="text-sm font-medium text-slate-900 dark:text-slate-100 mb-1">Schedule</p>
                        <p className="text-sm text-slate-600 dark:text-slate-400">
                            Updates automatically:
                            <br />
                            • <strong>Friday Fellowship</strong>: Mon - Fri 10pm
                            <br />
                            • <strong>Sunday Service</strong>: Fri 10pm - Sun
                        </p>
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
