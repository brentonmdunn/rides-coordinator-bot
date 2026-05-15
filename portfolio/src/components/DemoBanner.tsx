import { useState, useEffect } from 'react'

function DemoBanner() {
    const [toastVisible, setToastVisible] = useState(false)
    const [toastTimer, setToastTimer] = useState<ReturnType<typeof setTimeout> | null>(null)

    useEffect(() => {
        const handleDemoAction = () => {
            if (toastTimer) {
                clearTimeout(toastTimer)
            }
            setToastVisible(true)
            const timer = setTimeout(() => {
                setToastVisible(false)
            }, 3000)
            setToastTimer(timer)
        }

        window.addEventListener('demo-action', handleDemoAction)
        return () => {
            window.removeEventListener('demo-action', handleDemoAction)
            if (toastTimer) {
                clearTimeout(toastTimer)
            }
        }
    }, [toastTimer])

    return (
        <>
            <div className="sticky top-0 z-50 bg-info/10 border-b border-info/30 text-info-text px-4 py-2 text-center text-sm font-medium">
                Demo Mode — All data is fictional. No actions are executed.{' '}
                <a
                    href="https://github.com/brentonmdunn/rides-coordinator-bot"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="underline underline-offset-2 hover:opacity-75 transition-opacity"
                >
                    View source on GitHub
                </a>
            </div>
            {toastVisible && (
                <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 bg-card border border-border shadow-xl rounded-xl px-6 py-4 text-foreground flex items-center gap-3 whitespace-nowrap">
                    <div>
                        <p className="text-sm font-semibold">Demo Mode</p>
                        <p className="text-xs text-muted-foreground">In a live environment, this action would be executed.</p>
                    </div>
                </div>
            )}
        </>
    )
}

export default DemoBanner
