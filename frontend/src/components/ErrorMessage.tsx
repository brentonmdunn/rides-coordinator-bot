
interface ErrorMessageProps {
    message: string
}

export default function ErrorMessage({ message }: ErrorMessageProps) {
    if (!message) return null

    return (
        <div style={{
            color: '#b91c1c', // red-700
            marginBottom: '1em',
            padding: '1em',
            background: '#fef2f2', // red-50
            borderRadius: '6px',
            border: '1px solid #fecaca', // red-200
            display: 'flex',
            alignItems: 'flex-start',
            gap: '0.5em'
        }}>
            <span style={{ fontSize: '1.2em' }}>⚠️</span>
            <div>
                <strong style={{ display: 'block', marginBottom: '0.25em' }}>Error</strong>
                {message}
            </div>
        </div>
    )
}
