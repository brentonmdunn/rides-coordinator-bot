import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiFetch } from '../../lib/api'
import ErrorMessage from "../ErrorMessage"
import type { AskRidesStatus, FellowshipSeason } from '../../types'
import StatusCard from './StatusCard'
import { InfoToggleButton, InfoPanel } from '../InfoHelp'
import { ListSkeleton } from '../LoadingSkeleton'

import { CalendarDays, Settings } from 'lucide-react'
import { Button } from '../ui/button'
import ConfirmDialog from '../ConfirmDialog'
import { SectionCard } from '../shared'

interface AskRidesDashboardProps {
    canManage: boolean
}

function AskRidesDashboard({ canManage }: AskRidesDashboardProps) {
    const [showInfo, setShowInfo] = useState(false)
    const [showSettings, setShowSettings] = useState(false)
    const [showConfirm, setShowConfirm] = useState(false)
    const queryClient = useQueryClient()

    const {
        data: askRidesStatus,
        isLoading: askRidesLoading,
        error
    } = useQuery<AskRidesStatus>({
        queryKey: ['askRidesStatus'],
        queryFn: async () => {
            const response = await apiFetch('/api/ask-rides/status')
            return response.json()
        }
    })

    const { data: seasonData } = useQuery<{ season: FellowshipSeason }>({
        queryKey: ['fellowshipSeason'],
        queryFn: async () => {
            const response = await apiFetch('/api/ask-rides/fellowship-season')
            return response.json()
        },
    })

    const season = seasonData?.season ?? 'none'

    const seasonMutation = useMutation({
        mutationFn: async (newSeason: 'friday' | 'wednesday') => {
            const response = await apiFetch('/api/ask-rides/fellowship-season', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ season: newSeason }),
            })
            return response.json()
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['fellowshipSeason'] })
            queryClient.invalidateQueries({ queryKey: ['askRidesStatus'] })
        },
    })

    const sendNowMutation = useMutation({
        mutationFn: async () => {
            const response = await apiFetch('/api/ask-rides/send-now', {
                method: 'POST',
            })
            return response.json()
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['askRidesStatus'] })
        },
    })

    const handleSendNow = () => {
        setShowConfirm(false)
        sendNowMutation.mutate()
    }

    const askRidesError = error instanceof Error ? error.message : ''

    return (
        <SectionCard
            icon={<CalendarDays className="h-4 w-4" />}
            title="Ask Rides Status Dashboard"
            actions={
                <>
                    {canManage && (
                        <Button
                            onClick={() => setShowConfirm(true)}
                            disabled={sendNowMutation.isPending}
                            variant="warning"
                            size="sm"
                            className="hidden sm:flex gap-1.5"
                        >
                            {sendNowMutation.isPending ? (
                                <>
                                    <span className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                                    Sending...
                                </>
                            ) : (
                                '📨 Send now'
                            )}
                        </Button>
                    )}
                    {canManage && (
                        <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => { setShowSettings(!showSettings); setShowInfo(false) }}
                            className={`h-8 w-8 transition-colors ${showSettings ? 'text-foreground bg-muted' : 'text-muted-foreground hover:text-foreground'}`}
                            title="Dashboard settings"
                        >
                            <Settings className="h-5 w-5" />
                            <span className="sr-only">Dashboard settings</span>
                        </Button>
                    )}
                    <InfoToggleButton
                        isOpen={showInfo}
                        onClick={() => { setShowInfo(!showInfo); setShowSettings(false) }}
                        title="About Dashboard Status"
                    />
                </>
            }
        >
                {canManage && (
                    <Button
                        onClick={() => setShowConfirm(true)}
                        disabled={sendNowMutation.isPending}
                        variant="warning"
                        size="sm"
                        className="sm:hidden w-full gap-1.5 mb-4"
                    >
                        {sendNowMutation.isPending ? (
                            <>
                                <span className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                                Sending...
                            </>
                        ) : (
                            '📨 Send now'
                        )}
                    </Button>
                )}
                <InfoPanel
                    isOpen={showInfo}
                    onClose={() => setShowInfo(false)}
                    title="About Dashboard Status"
                >
                    <p className="mb-2">
                        This dashboard shows the current status of automated ride request jobs.
                    </p>
                    <ul className="space-y-1">
                        <li className="flex items-center gap-2">
                            <span className="w-2 h-2 rounded-full bg-info"></span>
                            <span><span className="font-medium">Will Send:</span> The job is scheduled and will run at the shown time.</span>
                        </li>
                        <li className="flex items-center gap-2">
                            <span className="w-2 h-2 rounded-full bg-success"></span>
                            <span><span className="font-medium">Message Sent:</span> A message has been sent for this week's ride requests.</span>
                        </li>
                        <li className="flex items-center gap-2">
                            <span className="w-2 h-2 rounded-full bg-warning"></span>
                            <span><span className="font-medium">Paused:</span> The job has been paused manually. It may resume automatically on a chosen date or stay paused until resumed.</span>
                        </li>
                        <li className="flex items-center gap-2">
                            <span className="w-2 h-2 rounded-full bg-warning"></span>
                            <span><span className="font-medium">Will Not Send:</span> Feature is enabled, but no action is needed (e.g., no class scheduled or a wildcard event was detected).</span>
                        </li>
                        <li className="flex items-center gap-2">
                            <span className="w-2 h-2 rounded-full bg-destructive"></span>
                            <span><span className="font-medium">Disabled:</span> The feature flag for this job is turned off.</span>
                        </li>
                    </ul>
                    <p className="mt-3 text-sm text-muted-foreground">
                        Use the <span className="font-medium">⏸️ Pause</span> / <span className="font-medium">▶️ Resume</span> buttons on each card to temporarily skip a job. Use the <span className="font-medium">📨 Send now</span> button to manually trigger all ask rides messages if the scheduled send was missed (e.g. due to a service crash).
                    </p>
                </InfoPanel>

                {sendNowMutation.isSuccess && (
                    <div className="mb-4 px-3 py-2 rounded-md bg-success/15 border border-success/30 text-success-text text-sm">
                        ✅ Ask rides messages sent successfully!
                    </div>
                )}

                {sendNowMutation.isError && (
                    <div className="mb-4 px-3 py-2 rounded-md bg-destructive/15 border border-destructive/30 text-destructive-text text-sm">
                        ❌ {sendNowMutation.error instanceof Error ? sendNowMutation.error.message : 'Failed to send messages'}
                    </div>
                )}

                {askRidesLoading && <ListSkeleton rows={3} />}

                <div className="mb-6">
                    <ErrorMessage message={askRidesError} />
                </div>

                {/* Settings panel */}
                {showSettings && canManage && (
                    <div className="mb-5 p-4 bg-muted/50 border border-border rounded-lg animate-in fade-in slide-in-from-top-2 duration-200">
                        <p className="text-sm font-medium text-foreground mb-3">Fellowship night</p>
                        <div className="inline-flex rounded-md border border-border overflow-hidden">
                            <button
                                onClick={() => seasonMutation.mutate('friday')}
                                disabled={seasonMutation.isPending}
                                className={`px-3 py-1.5 text-sm font-medium transition-colors border-r border-border ${
                                    season === 'friday'
                                        ? 'bg-info/15 text-info-text'
                                        : 'bg-background text-muted-foreground hover:bg-muted'
                                } disabled:opacity-50 disabled:cursor-not-allowed`}
                            >
                                🎓 Friday Fellowship
                            </button>
                            <button
                                onClick={() => seasonMutation.mutate('wednesday')}
                                disabled={seasonMutation.isPending}
                                className={`px-3 py-1.5 text-sm font-medium transition-colors ${
                                    season === 'wednesday'
                                        ? 'bg-info/15 text-info-text'
                                        : 'bg-background text-muted-foreground hover:bg-muted'
                                } disabled:opacity-50 disabled:cursor-not-allowed`}
                            >
                                ☀️ Wed. Fellowship
                            </button>
                        </div>
                        {seasonMutation.isError && (
                            <p className="mt-2 text-xs text-destructive-text">Failed to switch — try again</p>
                        )}
                    </div>
                )}

                {!askRidesLoading && !askRidesError && askRidesStatus && (
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                        {/* Fellowship card — Friday or Wednesday based on global setting */}
                        {season === 'wednesday'
                            ? <StatusCard title="Wed. Fellowship" jobName="wednesday" job={askRidesStatus.wednesday} canManage={canManage} />
                            : <StatusCard title="Friday Fellowship" jobName="friday" job={askRidesStatus.friday} canManage={canManage} />
                        }

                        {/* Sunday Service */}
                        <StatusCard title="Sunday Service" jobName="sunday" job={askRidesStatus.sunday} canManage={canManage} />

                        {/* Sunday Class */}
                        <StatusCard title="Sunday Class" jobName="sunday_class" job={askRidesStatus.sunday_class} canManage={canManage} />
                    </div>
                )}
            <ConfirmDialog
                isOpen={showConfirm}
                title="Send rides messages now?"
                description="This will immediately send the ask rides messages to the announcements channel. This action cannot be undone."
                confirmText="Yes, send now"
                onConfirm={handleSendNow}
                onCancel={() => setShowConfirm(false)}
            />
        </SectionCard>
    )
}

export default AskRidesDashboard
