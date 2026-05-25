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
                <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 bg-card border-2 border-info/40 shadow-2xl rounded-xl px-6 py-4 text-foreground flex items-center gap-4 whitespace-nowrap animate-in slide-in-from-bottom-4 fade-in duration-200">
                    <div className="flex-shrink-0 w-9 h-9 rounded-full bg-info/15 flex items-center justify-center">
                        <svg className="w-5 h-5 text-info-text" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" d="M11.25 11.25l.041-.02a.75.75 0 011.063.852l-.708 2.836a.75.75 0 001.063.853l.041-.021M21 12a9 9 0 11-18 0 9 9 0 0118 0zm-9-3.75h.008v.008H12V8.25z" />
                        </svg>
                    </div>
                    <div>
                        <p className="text-sm font-bold text-info-text">Demo Mode</p>
                        <p className="text-sm text-muted-foreground">In a live environment, this action would be executed.</p>
                    </div>
                </div>
            )}
        </>
    )
}

export default DemoBanner
