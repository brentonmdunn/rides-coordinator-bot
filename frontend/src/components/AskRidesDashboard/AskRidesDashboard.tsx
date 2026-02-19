import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiFetch } from '../../lib/api'
import ErrorMessage from "../ErrorMessage"
import type { AskRidesStatus } from '../../types'
import StatusCard from './StatusCard'
import { InfoToggleButton, InfoPanel } from '../InfoHelp'

import { Card, CardHeader, CardTitle, CardContent } from '../ui/card'
import { Button } from '../ui/button'

function AskRidesDashboard() {
    const [showInfo, setShowInfo] = useState(false)
    const [showConfirm, setShowConfirm] = useState(false)
    const queryClient = useQueryClient()

    const {
        data: askRidesStatus,
        isLoading: askRidesLoading,
        error
    } = useQuery<AskRidesStatus>({
        queryKey: ['askRidesStatus'],
        queryFn: async () => {
            // ... unchanged
            const response = await apiFetch('/api/ask-rides/status')
            if (!response.ok) {
                throw new Error('Failed to load ask rides status')
            }
            return response.json()
        }
    })

    const sendNowMutation = useMutation({
        mutationFn: async () => {
            const response = await apiFetch('/api/ask-rides/send-now', {
                method: 'POST',
            })
            if (!response.ok) {
                const data = await response.json().catch(() => ({}))
                throw new Error(data.detail || 'Failed to send messages')
            }
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
        <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle><span>📅</span> Ask Rides Status Dashboard</CardTitle>
                <div className="flex items-center gap-2">
                    <Button
                        onClick={() => setShowConfirm(true)}
                        disabled={sendNowMutation.isPending}
                        variant="warning"
                        size="sm"
                        className="gap-1.5"
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
                    <InfoToggleButton
                        isOpen={showInfo}
                        onClick={() => setShowInfo(!showInfo)}
                        title="About Dashboard Status"
                    />
                </div>
            </CardHeader>
            <CardContent>
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
                            <span><span className="font-medium">Will Not Send:</span> Feature is enabled, but no action is needed (e.g., no class scheduled).</span>
                        </li>
                        <li className="flex items-center gap-2">
                            <span className="w-2 h-2 rounded-full bg-destructive"></span>
                            <span><span className="font-medium">Disabled:</span> The feature flag for this job is turned off.</span>
                        </li>
                    </ul>
                    <p className="mt-3 text-sm text-slate-600 dark:text-slate-400">
                        Use the <span className="font-medium">📨 Send now</span> button to manually trigger all ask rides messages if the scheduled send was missed (e.g. due to a service crash).
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

                {askRidesLoading && (
                    <div className="p-8 text-center text-slate-500 animate-pulse">
                        Loading ask rides status...
                    </div>
                )}

                <div className="mb-6">
                    <ErrorMessage message={askRidesError} />
                </div>

                {!askRidesLoading && !askRidesError && askRidesStatus && (
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                        {/* Friday Fellowship */}
                        <StatusCard title="🎉 Friday Fellowship" jobName="friday" job={askRidesStatus.friday} />

                        {/* Sunday Service */}
                        <StatusCard title="⛪ Sunday Service" jobName="sunday" job={askRidesStatus.sunday} />

                        {/* Sunday Class */}
                        <StatusCard title="📖 Sunday Class" jobName="sunday_class" job={askRidesStatus.sunday_class} />
                    </div>
                )}
            </CardContent>

            {/* Confirmation Modal */}
            {showConfirm && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={() => setShowConfirm(false)}>
                    <div className="bg-white dark:bg-zinc-900 rounded-lg shadow-xl border border-slate-200 dark:border-zinc-700 p-6 max-w-sm mx-4" onClick={(e) => e.stopPropagation()}>
                        <h3 className="text-lg font-semibold text-slate-900 dark:text-white mb-2">
                            Send rides messages now?
                        </h3>
                        <p className="text-sm text-slate-600 dark:text-slate-400 mb-5">
                            This will immediately send the ask rides messages to the announcements channel. This action cannot be undone.
                        </p>
                        <div className="flex justify-end gap-3">
                            <button
                                onClick={() => setShowConfirm(false)}
                                className="px-4 py-2 text-sm font-medium rounded-md border border-slate-300 dark:border-zinc-600 text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-zinc-800 transition-colors"
                            >
                                Cancel
                            </button>
                            <button
                                onClick={handleSendNow}
                                className="px-4 py-2 text-sm font-medium rounded-md bg-blue-600 text-white hover:bg-blue-700 transition-colors"
                            >
                                Yes, send now
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </Card>
    )
}

export default AskRidesDashboard

