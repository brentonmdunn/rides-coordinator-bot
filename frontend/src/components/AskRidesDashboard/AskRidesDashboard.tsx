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
import { Switch } from '../ui/switch'
import ConfirmDialog from '../ConfirmDialog'
import { SectionCard } from '../shared'
import { CollapsibleSection } from '../ui/collapsible'
import MessageTemplatesEditor from './MessageTemplatesEditor'

interface AskRidesDashboardProps {
    canManage: boolean
}

type SendNowScope = 'fellowship' | 'sunday' | 'both'

function AskRidesDashboard({ canManage }: AskRidesDashboardProps) {
    const [showInfo, setShowInfo] = useState(false)
    const [showConfirm, setShowConfirm] = useState(false)
    const [sendScope, setSendScope] = useState<SendNowScope>('both')
    const [forceClass, setForceClass] = useState(false)
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
        mutationFn: async ({ scope, forceClass }: { scope: SendNowScope; forceClass: boolean }) => {
            const response = await apiFetch('/api/ask-rides/send-now', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ scope, force_class: forceClass }),
            })
            return response.json()
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['askRidesStatus'] })
        },
    })

    const { data: forceClassData } = useQuery<{ enabled: boolean }>({
        queryKey: ['forceSundayClass'],
        queryFn: async () => {
            const response = await apiFetch('/api/ask-rides/force-sunday-class')
            return response.json()
        },
    })

    const forceClassMutation = useMutation({
        mutationFn: async (enabled: boolean) => {
            const response = await apiFetch('/api/ask-rides/force-sunday-class', {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ enabled }),
            })
            return response.json()
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['forceSundayClass'] })
            queryClient.invalidateQueries({ queryKey: ['askRidesStatus'] })
        },
    })

    const handleSendNow = () => {
        setShowConfirm(false)
        sendNowMutation.mutate({ scope: sendScope, forceClass: forceClass && sendScope !== 'fellowship' })
    }

    const openSendConfirm = () => {
        setSendScope('both')
        setForceClass(false)
        setShowConfirm(true)
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
                            onClick={openSendConfirm}
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
                        onClick={openSendConfirm}
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
                        Use the <span className="font-medium">⏸️ Pause</span> / <span className="font-medium">▶️ Resume</span> buttons on each card to temporarily skip a job. Use the <span className="font-medium">📨 Send now</span> button to manually trigger ask rides messages if the scheduled send was missed (e.g. due to a service crash). During the Wed. fellowship season you can choose to send just the fellowship message, just Sunday, or both.
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

                {canManage && (
                    <label className="mt-6 flex items-start justify-between gap-4 rounded-md border border-border px-3 py-2 cursor-pointer">
                        <span className="text-sm">
                            <span className="font-medium">Always send Sunday class</span>
                            <span className="block text-muted-foreground">
                                The scheduled Sunday class message sends even if no class is on the calendar.
                            </span>
                        </span>
                        <Switch
                            checked={forceClassData?.enabled ?? false}
                            disabled={forceClassData === undefined || forceClassMutation.isPending}
                            onCheckedChange={(checked) => forceClassMutation.mutate(checked)}
                            aria-label="Always send Sunday class"
                        />
                    </label>
                )}

                {canManage && (
                    <div className="mt-6">
                        <CollapsibleSection title="Message Templates">
                            <div className="p-4 sm:p-5">
                                <MessageTemplatesEditor />
                            </div>
                        </CollapsibleSection>
                    </div>
                )}
            <ConfirmDialog
                isOpen={showConfirm}
                title="Send rides messages now?"
                description={season === 'wednesday'
                    ? 'This will immediately send the selected ask rides messages to the announcements channel. This action cannot be undone.'
                    : 'This will immediately send all ask rides messages to the announcements channel. This action cannot be undone.'}
                confirmText="Yes, send now"
                onConfirm={handleSendNow}
                onCancel={() => setShowConfirm(false)}
            >
                {/* Friday and Sunday send together, so the scope picker only makes
                    sense during the Wednesday fellowship season. */}
                {season === 'wednesday' && (
                    <div className="flex flex-col gap-1.5 py-2">
                        {(
                            [
                                { value: 'fellowship', label: fellowshipLabel },
                                { value: 'sunday', label: 'Sunday' },
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
                )}
                {sendScope !== 'fellowship' && (
                    <label className="flex items-start gap-2 rounded-md border border-border px-3 py-2 mt-2 cursor-pointer has-[:checked]:border-primary has-[:checked]:bg-primary/5">
                        <input
                            type="checkbox"
                            checked={forceClass}
                            onChange={(e) => setForceClass(e.target.checked)}
                            className="accent-primary mt-0.5"
                        />
                        <span className="text-sm">
                            Send the Sunday class message even if no class is on the calendar
                        </span>
                    </label>
                )}
            </ConfirmDialog>
        </SectionCard>
    )
}

export default AskRidesDashboard
