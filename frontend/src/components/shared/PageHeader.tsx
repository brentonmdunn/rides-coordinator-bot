import type { ReactNode } from 'react'

interface PageHeaderProps {
    /** Optional small content rendered above the title (e.g. a back link). */
    eyebrow?: ReactNode
    title: ReactNode
    description?: ReactNode
    /** Action area on the right side (e.g. Learn button + ModeToggle). */
    actions?: ReactNode
    /** Center the title block on small screens. */
    centerOnMobile?: boolean
}

/**
 * Standardized page header used across top-level pages — title, description
 * and an optional actions area on the right (for example the dark-mode
 * toggle).
 */
function PageHeader({
    eyebrow,
    title,
    description,
    actions,
    centerOnMobile = false,
}: PageHeaderProps) {
    const titleAlign = centerOnMobile ? 'text-center md:text-left' : ''
    const descriptionAlign = centerOnMobile ? 'mx-auto md:mx-0' : ''
    const actionsAlign = centerOnMobile
        ? 'justify-center md:justify-end'
        : 'justify-center md:justify-end'

    return (
        <header className="flex flex-col md:flex-row md:items-start md:justify-between gap-6 mb-12">
            <div className={`flex-1 ${titleAlign}`}>
                {eyebrow}
                <h1 className="text-4xl font-extrabold tracking-tight text-slate-900 dark:text-white sm:text-5xl mb-4">
                    {title}
                </h1>
                {description != null && (
                    <p
                        className={`text-lg text-slate-600 dark:text-slate-400 max-w-2xl ${descriptionAlign}`.trim()}
                    >
                        {description}
                    </p>
                )}
            </div>
            {actions != null && (
                <div className={`flex items-center gap-3 ${actionsAlign}`}>
                    {actions}
                </div>
            )}
        </header>
    )
}

export default PageHeader
