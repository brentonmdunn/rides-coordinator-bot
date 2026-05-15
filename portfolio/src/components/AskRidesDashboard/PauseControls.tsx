import { useState } from 'react'
import { useQuery, useMutation, useQueryClient, keepPreviousData } from '@tanstack/react-query'
import { apiFetch } from '../../lib/api'
import { UPCOMING_DATES_PAGE_SIZE } from '../../lib/constants'
import { Button } from '../ui/button'
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogHeader,
    DialogTitle,
} from '../ui/dialog'
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

    const { data: upcomingDates, isLoading: datesLoading } = useQuery<{ dates: UpcomingDate[]; has_more: boolean }>({
        queryKey: ['upcomingDates', jobName, dateOffset],
        queryFn: async () => {
            const response = await apiFetch(`/api/ask-rides/upcoming-dates/${jobName}?count=${UPCOMING_DATES_PAGE_SIZE}&offset=${dateOffset}`)
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
                        'Resume'
                    )}
                </Button>
            ) : (
                <Button
                    onClick={() => setShowModal(true)}
                    variant="outline"
                    size="sm"
                    className="gap-1.5 w-full"
                >
                    Pause
                </Button>
            )}

            <Dialog open={showModal} onOpenChange={(open) => { if (!open) setShowModal(false) }}>
                <DialogContent className="sm:max-w-sm">
                    <DialogHeader>
                        <DialogTitle>Pause messages</DialogTitle>
                        <DialogDescription>
                            Skip sending until you resume or until a specific event.
                        </DialogDescription>
                    </DialogHeader>

                    <div className="flex flex-col gap-2">
                        {/* Indefinite pause */}
                        <Button
                            variant="outline"
                            onClick={() => pauseMutation.mutate({ is_paused: true, resume_after_date: null })}
                            disabled={pauseMutation.isPending}
                            className="w-full h-auto flex-col items-start px-4 py-3 text-left"
                        >
                            <div className="font-medium">Pause indefinitely</div>
                            <div className="text-sm text-muted-foreground mt-0.5 font-normal">
                                Manually resume when ready
                            </div>
                        </Button>

                        {/* Divider with date navigation */}
                        <div className="flex items-center gap-3 my-1">
                            <div className="flex-1 h-px bg-border" />
                            <div className="flex items-center gap-1">
                                <Button
                                    variant="ghost"
                                    size="icon-sm"
                                    onClick={() => setDateOffset((prev) => Math.max(0, prev - UPCOMING_DATES_PAGE_SIZE))}
                                    disabled={dateOffset === 0}
                                    aria-label="Previous dates"
                                >
                                    ←
                                </Button>
                                <span className="text-xs text-muted-foreground uppercase tracking-wide font-medium px-1">
                                    or skip until
                                </span>
                                <Button
                                    variant="ghost"
                                    size="icon-sm"
                                    onClick={() => setDateOffset((prev) => prev + UPCOMING_DATES_PAGE_SIZE)}
                                    aria-label="Next dates"
                                >
                                    →
                                </Button>
                            </div>
                            <div className="flex-1 h-px bg-border" />
                        </div>

                        {/* Date cards */}
                        {datesLoading ? (
                            <div className="py-4 text-center text-muted-foreground animate-pulse text-sm">
                                Loading upcoming dates...
                            </div>
                        ) : (
                            upcomingDates?.dates.map((d: UpcomingDate) => (
                                <Button
                                    key={d.event_date}
                                    variant="outline"
                                    onClick={() => pauseMutation.mutate({ is_paused: true, resume_after_date: d.event_date })}
                                    disabled={pauseMutation.isPending}
                                    className="w-full h-auto flex items-center justify-between px-4 py-2.5 text-left hover:bg-info/10 hover:border-info/40"
                                >
                                    <span className="font-medium">
                                        {formatEventDate(d.event_date)}
                                    </span>
                                    <span className="text-xs text-muted-foreground font-normal">
                                        sends {formatEventDate(d.send_date)}
                                    </span>
                                </Button>
                            ))
                        )}
                    </div>

                    {pauseMutation.isError && (
                        <div className="px-3 py-2 rounded-md bg-destructive/15 text-destructive-text text-sm">
                            ❌ {pauseMutation.error instanceof Error ? pauseMutation.error.message : 'Failed to update pause'}
                        </div>
                    )}
                </DialogContent>
            </Dialog>
        </>
    )
}

export default PauseControls
