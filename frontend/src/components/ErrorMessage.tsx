
interface ErrorMessageProps {
    message: string
}

export default function ErrorMessage({ message }: ErrorMessageProps) {
    if (!message) return null

    return (
        <div className="mb-4 p-4 text-red-700 bg-red-50 border border-red-200 rounded-lg flex items-start gap-2 dark:bg-red-900/10 dark:text-red-400 dark:border-red-900/50">
            <span className="text-lg">⚠️</span>
            <div>
                <strong className="block mb-1 font-semibold">Error</strong>
                {message}
            </div>
        </div>
    )
}
