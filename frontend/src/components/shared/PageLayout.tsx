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
                className="relative min-h-screen w-full max-w-[100vw] bg-background py-12 px-4 font-sans text-foreground transition-colors duration-300"
            >
                {/* Cohere mesh gradient wash — subtle behind-the-fold decoration */}
                <div className="pointer-events-none absolute inset-0 cohere-mesh opacity-60" />
                <div
                    className={
                        spacedBody
                            ? 'relative max-w-5xl mx-auto space-y-8'
                            : 'relative max-w-5xl mx-auto'
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
