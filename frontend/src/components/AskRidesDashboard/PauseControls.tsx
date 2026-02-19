import { useState } from 'react'
import { useQuery, useMutation, useQueryClient, keepPreviousData } from '@tanstack/react-query'
import { apiFetch } from '../../lib/api'
import { Button } from '../ui/button'
import type { AskRidesJobStatus, UpcomingDate } from '../../types'

interface PauseControlsProps {
    jobName: string
    job: AskRidesJobStatus
}

const formatEventDate = (isoDate: string): string => {
    const date = new Date(isoDate + 'T12:00:00')
    return date.toLocaleDateString('en-US', {
        weekday: 'short',
        month: 'short',
        day: 'numeric',
    })
}

function PauseControls({ jobName, job }: PauseControlsProps) {
    const [showModal, setShowModal] = useState(false)
    const [dateOffset, setDateOffset] = useState(0)
    const queryClient = useQueryClient()

    const isPaused = job.pause?.is_paused ?? false

    // Always fetch initial dates when the modal is open — lightweight call
    const { data: upcomingDates, isLoading: datesLoading } = useQuery<{ dates: UpcomingDate[]; has_more: boolean }>({
        queryKey: ['upcomingDates', jobName, dateOffset],
        queryFn: async () => {
            const response = await apiFetch(`/api/ask-rides/upcoming-dates/${jobName}?count=4&offset=${dateOffset}`)
            if (!response.ok) throw new Error('Failed to load dates')
            return response.json()
        },
        enabled: showModal,
        placeholderData: keepPreviousData,
    })

    const pauseMutation = useMutation({
        mutationFn: async (params: { is_paused: boolean; resume_after_date?: string | null }) => {
            const response = await apiFetch(`/api/ask-rides/pauses/${jobName}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(params),
            })
            if (!response.ok) {
                const data = await response.json().catch(() => ({}))
                throw new Error(data.detail || 'Failed to update pause')
            }
            return response.json()
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['askRidesStatus'] })
            setShowModal(false)
        },
    })

    const handleResume = () => {
        pauseMutation.mutate({ is_paused: false })
    }

    // Don't show controls if the feature flag is off
    if (!job.enabled) return null

    return (
        <>
            {isPaused ? (
                <Button
                    onClick={handleResume}
                    disabled={pauseMutation.isPending}
                    variant="outline"
                    size="sm"
                    className="gap-1.5 w-full"
                >
                    {pauseMutation.isPending ? (
                        <>
                            <span className="w-3 h-3 border-2 border-current/30 border-t-current rounded-full animate-spin" />
                            Resuming...
                        </>
                    ) : (
                        '▶️ Resume'
                    )}
                </Button>
            ) : (
                <Button
                    onClick={() => setShowModal(true)}
                    variant="outline"
                    size="sm"
                    className="gap-1.5 w-full"
                >
                    ⏸️ Pause
                </Button>
            )}

            {/* Pause Modal — single-screen with all options visible */}
            {showModal && (
                <div
                    className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
                    onClick={() => setShowModal(false)}
                >
                    <div
                        className="bg-white dark:bg-zinc-900 rounded-lg shadow-xl border border-slate-200 dark:border-zinc-700 p-6 max-w-sm mx-4 w-full"
                        onClick={(e) => e.stopPropagation()}
                    >
                        <h3 className="text-lg font-semibold text-slate-900 dark:text-white mb-1">
                            Pause messages
                        </h3>
                        <p className="text-sm text-slate-500 dark:text-slate-400 mb-5">
                            Skip sending until you resume or until a specific event.
                        </p>

                        <div className="flex flex-col gap-2">
                            {/* Indefinite pause — always available */}
                            <button
                                onClick={() => pauseMutation.mutate({ is_paused: true, resume_after_date: null })}
                                disabled={pauseMutation.isPending}
                                className="w-full text-left px-4 py-3 rounded-md border border-slate-200 dark:border-zinc-700 hover:bg-slate-50 dark:hover:bg-zinc-800 hover:border-slate-300 dark:hover:border-zinc-600 transition-colors"
                            >
                                <div className="font-medium text-slate-900 dark:text-white">Pause indefinitely</div>
                                <div className="text-sm text-slate-500 dark:text-slate-400 mt-0.5">
                                    Manually resume when ready
                                </div>
                            </button>

                            {/* Divider with date navigation */}
                            <div className="flex items-center gap-3 my-1">
                                <div className="flex-1 h-px bg-slate-200 dark:bg-zinc-700" />
                                <div className="flex items-center gap-2">
                                    <button
                                        onClick={() => setDateOffset((prev) => Math.max(0, prev - 4))}
                                        disabled={dateOffset === 0}
                                        className="p-2 text-slate-400 dark:text-slate-500 hover:text-slate-600 dark:hover:text-slate-300 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
                                        aria-label="Previous dates"
                                    >
                                        ←
                                    </button>
                                    <span className="text-xs text-slate-400 dark:text-slate-500 uppercase tracking-wide font-medium">
                                        or skip until
                                    </span>
                                    <button
                                        onClick={() => setDateOffset((prev) => prev + 4)}
                                        className="p-2 text-slate-400 dark:text-slate-500 hover:text-slate-600 dark:hover:text-slate-300 transition-colors"
                                        aria-label="Next dates"
                                    >
                                        →
                                    </button>
                                </div>
                                <div className="flex-1 h-px bg-slate-200 dark:bg-zinc-700" />
                            </div>

                            {/* Date cards */}
                            {datesLoading ? (
                                <div className="py-4 text-center text-slate-500 animate-pulse text-sm">
                                    Loading upcoming dates...
                                </div>
                            ) : (
                                upcomingDates?.dates.map((d: UpcomingDate) => (
                                    <button
                                        key={d.event_date}
                                        onClick={() => pauseMutation.mutate({ is_paused: true, resume_after_date: d.event_date })}
                                        disabled={pauseMutation.isPending}
                                        className="w-full text-left px-4 py-2.5 rounded-md border border-slate-200 dark:border-zinc-700 hover:bg-blue-50 dark:hover:bg-blue-950/30 hover:border-blue-300 dark:hover:border-blue-800 transition-colors group"
                                    >
                                        <div className="flex items-center justify-between">
                                            <span className="font-medium text-slate-900 dark:text-white">
                                                {formatEventDate(d.event_date)}
                                            </span>
                                            <span className="text-xs text-slate-400 dark:text-slate-500 group-hover:text-blue-500 transition-colors">
                                                sends {formatEventDate(d.send_date)}
                                            </span>
                                        </div>
                                    </button>
                                ))
                            )}
                        </div>

                        {/* Cancel */}
                        <div className="mt-4 flex justify-end">
                            <button
                                onClick={() => setShowModal(false)}
                                className="px-4 py-2 text-sm font-medium rounded-md border border-slate-300 dark:border-zinc-600 text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-zinc-800 transition-colors"
                            >
                                Cancel
                            </button>
                        </div>

                        {pauseMutation.isError && (
                            <div className="mt-3 px-3 py-2 rounded-md bg-destructive/15 text-destructive-text text-sm">
                                ❌ {pauseMutation.error instanceof Error ? pauseMutation.error.message : 'Failed to update pause'}
                            </div>
                        )}
                    </div>
                </div>
            )}
        </>
    )
}

export default PauseControls
