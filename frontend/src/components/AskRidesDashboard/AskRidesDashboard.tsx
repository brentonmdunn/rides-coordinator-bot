import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiFetch } from '../../lib/api'
import ErrorMessage from "../ErrorMessage"
import type { AskRidesStatus, FellowshipSeason } from '../../types'
import StatusCard from './StatusCard'
import { InfoToggleButton, InfoPanel } from '../InfoHelp'
import { ListSkeleton } from '../LoadingSkeleton'

import { CalendarDays } from 'lucide-react'
import { Button } from '../ui/button'
import ConfirmDialog from '../ConfirmDialog'
import { SectionCard } from '../shared'

interface AskRidesDashboardProps {
    canManage: boolean
}

type SendNowScope = 'fellowship' | 'sunday' | 'both'

function AskRidesDashboard({ canManage }: AskRidesDashboardProps) {
    const [showInfo, setShowInfo] = useState(false)
    const [showConfirm, setShowConfirm] = useState(false)
    const [sendScope, setSendScope] = useState<SendNowScope>('both')
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

    const season = seasonData?.season ?? 'friday'

    const sendNowMutation = useMutation({
        mutationFn: async (scope: SendNowScope) => {
            const response = await apiFetch('/api/ask-rides/send-now', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ scope }),
            })
            return response.json()
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['askRidesStatus'] })
        },
    })

    const handleSendNow = () => {
        setShowConfirm(false)
        sendNowMutation.mutate(sendScope)
    }

    const fellowshipLabel = season === 'wednesday' ? 'Wed. Fellowship' : 'Fri. Fellowship'

    const askRidesError = error instanceof Error ? error.message : ''

    return (
        <SectionCard
            icon={<CalendarDays className="h-4 w-4" />}
            title="Ask Rides Status Dashboard"
            actions={
                <>
                    {canManage && (
                        <Button
                            onClick={() => { setSendScope('both'); setShowConfirm(true) }}
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
                    <InfoToggleButton
                        isOpen={showInfo}
                        onClick={() => setShowInfo(!showInfo)}
                        title="About Dashboard Status"
                    />
                </>
            }
        >
                {canManage && (
                    <Button
                        onClick={() => { setSendScope('both'); setShowConfirm(true) }}
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
                        Use the <span className="font-medium">⏸️ Pause</span> / <span className="font-medium">▶️ Resume</span> buttons on each card to temporarily skip a job. Use the <span className="font-medium">📨 Send now</span> button to manually trigger ask rides messages if the scheduled send was missed (e.g. due to a service crash) — you can choose to send just the fellowship message, just Sunday, or both.
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
                description="This will immediately send the selected ask rides messages to the announcements channel. This action cannot be undone."
                confirmText="Yes, send now"
                onConfirm={handleSendNow}
                onCancel={() => setShowConfirm(false)}
            >
                <div className="flex flex-col gap-1.5 py-2">
                    {(
                        [
                            { value: 'fellowship', label: fellowshipLabel },
                            { value: 'sunday', label: 'Sunday (service + class)' },
                            { value: 'both', label: 'Both' },
                        ] as const
                    ).map((option) => (
                        <label
                            key={option.value}
                            className="flex items-center gap-2 rounded-md border border-border px-3 py-2 cursor-pointer has-[:checked]:border-primary has-[:checked]:bg-primary/5"
                        >
                            <input
                                type="radio"
                                name="send-now-scope"
                                value={option.value}
                                checked={sendScope === option.value}
                                onChange={() => setSendScope(option.value)}
                                className="accent-primary"
                            />
                            <span className="text-sm">{option.label}</span>
                        </label>
                    ))}
                </div>
            </ConfirmDialog>
        </SectionCard>
    )
}

export default AskRidesDashboard
