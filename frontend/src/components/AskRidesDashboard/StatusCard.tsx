import type { AskRidesJobStatus } from '../../types'

interface StatusCardProps {
    title: string
    job: AskRidesJobStatus
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

const getStatusBadge = (job: AskRidesJobStatus) => {
    if (!job.enabled) {
        return { color: '#ef4444', text: '🔴 Feature flag disabled' }
    }
    if (job.sent_this_week) {
        return { color: '#3b82f6', text: '🔵 Message sent for this week' }
    }
    if (!job.will_send) {
        const reasonText = job.reason === 'wildcard_detected'
            ? 'Wildcard event detected'
            : 'No class scheduled'
        return { color: '#eab308', text: `🟡 Will not send - ${reasonText} ` }
    }
    return { color: '#22c55e', text: `🟢 Will send at ${formatDateTime(job.next_run)} ` }
}

function StatusCard({ title, job }: StatusCardProps) {
    const status = getStatusBadge(job)

    // Helper map for better color handling in Tailwind
    const getStatusColors = (color: string) => {
        if (color === '#ef4444') return 'bg-red-50 text-red-700 border-red-100 dark:bg-red-900/20 dark:text-red-300 dark:border-red-800'
        if (color === '#eab308') return 'bg-yellow-50 text-yellow-700 border-yellow-100 dark:bg-yellow-900/20 dark:text-yellow-300 dark:border-yellow-800'
        if (color === '#3b82f6') return 'bg-blue-50 text-blue-700 border-blue-100 dark:bg-blue-900/20 dark:text-blue-300 dark:border-blue-800'
        return 'bg-green-50 text-green-700 border-green-100 dark:bg-green-900/20 dark:text-green-300 dark:border-green-800'
    }

    return (
        <div className="bg-white dark:bg-zinc-900 rounded-lg border border-slate-200 dark:border-zinc-800 p-5 shadow-sm hover:shadow-md transition-shadow">
            <h3 className="text-lg font-semibold text-slate-900 dark:text-white mb-3">{title}</h3>

            <div className={`px-3 py-2 rounded-md border text-sm font-medium mb-4 ${getStatusColors(status.color)}`}>
                {status.text}
            </div>

            {job.last_message && (
                <div className="pt-3 border-t border-slate-100 dark:border-zinc-800 text-sm">
                    <strong className="block text-slate-700 dark:text-slate-300 mb-2">Last message reactions</strong>
                    <div className="flex flex-wrap gap-3">
                        {Object.entries(job.last_message.reactions).map(([emoji, count]) => (
                            <span key={emoji} className="inline-flex items-center gap-1.5 px-2 py-1 bg-slate-100 dark:bg-zinc-800 rounded text-slate-700 dark:text-slate-300">
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
