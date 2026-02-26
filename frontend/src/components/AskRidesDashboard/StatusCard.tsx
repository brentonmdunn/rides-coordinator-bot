import type { AskRidesJobStatus } from '../../types'
import PauseControls from './PauseControls'

interface StatusCardProps {
    title: string
    jobName: string
    job: AskRidesJobStatus
    canManage: boolean
}

const formatDateTime = (isoString: string): string => {
    const date = new Date(isoString)
    return date.toLocaleString('en-US', {
        weekday: 'short',
        month: 'short',
        day: 'numeric',
        hour: 'numeric',
        minute: '2-digit',
        hour12: true
    })
}

const formatDate = (isoDate: string): string => {
    const date = new Date(isoDate + 'T12:00:00')
    return date.toLocaleDateString('en-US', {
        weekday: 'short',
        month: 'short',
        day: 'numeric',
    })
}

const getStatusBadge = (job: AskRidesJobStatus) => {
    if (!job.enabled) {
        return { color: '#ef4444', text: '🔴 Feature flag disabled' }
    }
    if (job.pause?.is_paused) {
        if (job.pause.resume_after_date) {
            return {
                color: '#eab308',
                text: `⏸️ Paused — resumes ${formatDate(job.pause.resume_send_date ?? job.pause.resume_after_date)} for ${formatDate(job.pause.resume_after_date)}`
            }
        }
        return { color: '#eab308', text: '⏸️ Paused indefinitely' }
    }
    if (job.sent_this_week) {
        return { color: '#22c55e', text: '🟢 Message sent for this week' }
    }
    if (!job.will_send) {
        const reasonText = job.reason === 'wildcard_detected'
            ? 'Wildcard event detected'
            : 'No class scheduled'
        return { color: '#eab308', text: `🟡 Will not send - ${reasonText} ` }
    }
    return { color: '#3b82f6', text: `🔵 Will send at ${formatDateTime(job.next_run)} ` }
}

function StatusCard({ title, jobName, job, canManage }: StatusCardProps) {
    const status = getStatusBadge(job)

    // Helper map for better color handling in Tailwind
    const getStatusColors = (color: string) => {
        if (color === '#ef4444') return 'bg-destructive/15 text-destructive-text border-destructive/30'
        if (color === '#eab308') return 'bg-warning/15 text-warning-text border-warning/50'
        if (color === '#3b82f6') return 'bg-info/15 text-info-text border-info/30'
        return 'bg-success/15 text-success-text border-success/30'
    }

    return (
        <div className="bg-card rounded-lg border border-border p-5 shadow-sm hover:shadow-md transition-shadow">
            <h3 className="text-lg font-semibold text-foreground mb-3">{title}</h3>

            <div className={`px-3 py-2 rounded-md border text-sm font-medium mb-4 whitespace-normal break-words ${getStatusColors(status.color)}`}>
                {status.text}
            </div>

            {canManage && (
                <div className="mb-4">
                    <PauseControls jobName={jobName} job={job} />
                </div>
            )}

            {job.last_message && (
                <div className="pt-3 border-t border-border text-sm">
                    <strong className="block text-muted-foreground mb-2">Message reactions</strong>
                    <div className="flex flex-wrap gap-3">
                        {Object.entries(job.last_message.reactions).map(([emoji, count]) => (
                            <span key={emoji} className="inline-flex items-center gap-1.5 px-2 py-1 bg-muted rounded text-foreground">
                                <span className="text-base">{emoji}</span>
                                <span className="font-mono font-medium">{count}</span>
                            </span>
                        ))}
                    </div>
                </div>
            )}
        </div>
    )
}

export default StatusCard

