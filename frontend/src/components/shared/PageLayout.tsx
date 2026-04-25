import type { ReactNode } from 'react'
import EnvironmentBanner from '../EnvironmentBanner'

interface PageLayoutProps {
    /** Page-level header (typically <PageHeader />). */
    header: ReactNode
    /** Wrap the body in `space-y-8` to match the dashboard layout. */
    spacedBody?: boolean
    children: ReactNode
}

/**
 * Top-level page chrome shared by the dashboard and tutorial pages — the
 * environment banner + the standard `<main>` shell + a centered max-width
 * container.
 */
function PageLayout({ header, spacedBody = false, children }: PageLayoutProps) {
    return (
        <>
            <EnvironmentBanner />
            <main
                id="main-content"
                className="min-h-screen w-full max-w-[100vw] overflow-x-hidden bg-gray-50 dark:bg-zinc-950 py-12 px-4 font-sans text-slate-900 dark:text-slate-100 transition-colors duration-300"
            >
                <div
                    className={
                        spacedBody
                            ? 'max-w-4xl mx-auto space-y-8 overflow-x-hidden'
                            : 'max-w-4xl mx-auto'
                    }
                >
                    {header}
                    {children}
                </div>
            </main>
        </>
    )
}

export default PageLayout
