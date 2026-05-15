
interface ErrorMessageProps {
    message: string
}

export default function ErrorMessage({ message }: ErrorMessageProps) {
    if (!message) return null

    return (
        <div className="mb-4 p-4 text-destructive-text bg-destructive/10 border border-destructive/30 rounded-lg flex items-start gap-2">
            <span className="text-lg">⚠️</span>
            <div>
                <strong className="block mb-1 font-semibold">Error</strong>
                {message}
            </div>
        </div>
    )
}
