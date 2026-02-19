import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiFetch } from '../../lib/api'
import { Button } from '../ui/button'
import { Select } from '../ui/select'
import type { AskRidesJobStatus, UpcomingDate } from '../../types'

type PauseMode = 'choose' | 'indefinite' | 'until-date'

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
    const [pauseMode, setPauseMode] = useState<PauseMode>('choose')
    const [selectedDate, setSelectedDate] = useState<string | null>(null)
    const [dateOffset, setDateOffset] = useState(0)
    const queryClient = useQueryClient()

    const isPaused = job.pause?.is_paused ?? false

    // Fetch upcoming dates when in date selection mode
    const { data: upcomingDates, isLoading: datesLoading } = useQuery<{ dates: UpcomingDate[]; has_more: boolean }>({
        queryKey: ['upcomingDates', jobName, dateOffset],
        queryFn: async () => {
            const response = await apiFetch(`/api/ask-rides/upcoming-dates/${jobName}?count=6&offset=${dateOffset}`)
            if (!response.ok) throw new Error('Failed to load dates')
            return response.json()
        },
        enabled: pauseMode === 'until-date' && showModal,
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
            resetModal()
        },
    })

    const resetModal = () => {
        setPauseMode('choose')
        setSelectedDate(null)
        setDateOffset(0)
    }

    const handleOpenModal = () => {
        resetModal()
        setShowModal(true)
    }

    const handleResume = () => {
        pauseMutation.mutate({ is_paused: false })
    }

    const handlePauseIndefinitely = () => {
        pauseMutation.mutate({ is_paused: true, resume_after_date: null })
    }

    const handlePauseUntilDate = () => {
        if (!selectedDate) return
        pauseMutation.mutate({ is_paused: true, resume_after_date: selectedDate })
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
                    onClick={handleOpenModal}
                    variant="outline"
                    size="sm"
                    className="gap-1.5 w-full"
                >
                    ⏸️ Pause
                </Button>
            )}

            {/* Pause Modal */}
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
                            Choose how to pause this job's messages.
                        </p>

                        {pauseMode === 'choose' && (
                            <div className="flex flex-col gap-3">
                                <button
                                    onClick={() => handlePauseIndefinitely()}
                                    disabled={pauseMutation.isPending}
                                    className="w-full text-left px-4 py-3 rounded-md border border-slate-200 dark:border-zinc-700 hover:bg-slate-50 dark:hover:bg-zinc-800 transition-colors"
                                >
                                    <div className="font-medium text-slate-900 dark:text-white">Pause indefinitely</div>
                                    <div className="text-sm text-slate-500 dark:text-slate-400 mt-0.5">
                                        Messages won't be sent until you manually resume.
                                    </div>
                                </button>
                                <button
                                    onClick={() => setPauseMode('until-date')}
                                    className="w-full text-left px-4 py-3 rounded-md border border-slate-200 dark:border-zinc-700 hover:bg-slate-50 dark:hover:bg-zinc-800 transition-colors"
                                >
                                    <div className="font-medium text-slate-900 dark:text-white">Pause until a specific date</div>
                                    <div className="text-sm text-slate-500 dark:text-slate-400 mt-0.5">
                                        Messages will automatically resume before the selected date.
                                    </div>
                                </button>
                            </div>
                        )}

                        {pauseMode === 'until-date' && (
                            <div className="flex flex-col gap-4">
                                <div>
                                    <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                                        Resume before which date?
                                    </label>
                                    {datesLoading ? (
                                        <div className="py-3 text-center text-slate-500 animate-pulse text-sm">
                                            Loading dates...
                                        </div>
                                    ) : (
                                        <>
                                            <Select
                                                value={selectedDate ?? ''}
                                                onChange={(e) => setSelectedDate(e.target.value || null)}
                                            >
                                                <option value="">Select a date...</option>
                                                {upcomingDates?.dates.map((d) => (
                                                    <option key={d.event_date} value={d.event_date}>
                                                        {d.label} (sends {formatEventDate(d.send_date)})
                                                    </option>
                                                ))}
                                            </Select>
                                            <button
                                                onClick={() => setDateOffset((prev) => prev + 6)}
                                                className="mt-2 text-sm text-blue-600 dark:text-blue-400 hover:underline"
                                            >
                                                Load later dates →
                                            </button>
                                        </>
                                    )}
                                </div>

                                {selectedDate && (
                                    <div className="px-3 py-2 rounded-md bg-info/10 border border-info/20 text-sm text-slate-700 dark:text-slate-300">
                                        Messages will resume on <strong>{formatEventDate(
                                            upcomingDates?.dates.find(d => d.event_date === selectedDate)?.send_date ?? selectedDate
                                        )}</strong> for the <strong>{formatEventDate(selectedDate)}</strong> event.
                                    </div>
                                )}

                                <div className="flex justify-end gap-3">
                                    <button
                                        onClick={() => setPauseMode('choose')}
                                        className="px-4 py-2 text-sm font-medium rounded-md border border-slate-300 dark:border-zinc-600 text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-zinc-800 transition-colors"
                                    >
                                        Back
                                    </button>
                                    <button
                                        onClick={handlePauseUntilDate}
                                        disabled={!selectedDate || pauseMutation.isPending}
                                        className="px-4 py-2 text-sm font-medium rounded-md bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                                    >
                                        {pauseMutation.isPending ? 'Pausing...' : 'Confirm pause'}
                                    </button>
                                </div>
                            </div>
                        )}

                        {pauseMode === 'choose' && (
                            <div className="mt-4 flex justify-end">
                                <button
                                    onClick={() => setShowModal(false)}
                                    className="px-4 py-2 text-sm font-medium rounded-md border border-slate-300 dark:border-zinc-600 text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-zinc-800 transition-colors"
                                >
                                    Cancel
                                </button>
                            </div>
                        )}

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
