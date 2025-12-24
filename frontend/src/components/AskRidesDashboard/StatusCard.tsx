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

    return (
        <div style={{
            border: '1px solid #ddd',
            borderRadius: '8px',
            padding: '1em',
            background: '#f9f9f9'
        }}>
            <h3 style={{ marginTop: 0, marginBottom: '0.5em' }}>{title}</h3>
            <div style={{
                padding: '0.5em',
                borderRadius: '4px',
                background: status.color + '22',
                color: status.color,
                fontWeight: 'bold',
                marginBottom: '0.5em'
            }}>
                {status.text}
            </div>
            {job.last_message && (
                <div style={{ marginTop: '0.5em', fontSize: '0.9em' }}>
                    <strong>Last message reactions:</strong>
                    <div style={{ marginTop: '0.25em' }}>
                        {Object.entries(job.last_message.reactions).map(([emoji, count]) => (
                            <span key={emoji} style={{ marginRight: '0.75em' }}>
                                {emoji} {count}
                            </span>
                        ))}
                    </div>
                </div>
            )}
        </div>
    )
}

export default StatusCard
