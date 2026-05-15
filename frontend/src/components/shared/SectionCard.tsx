import type { ReactNode } from 'react'
import { Card, CardHeader, CardTitle, CardContent } from '../ui/card'
import { cn } from '@/lib/utils'

interface SectionCardProps {
    /** An emoji string or icon node rendered before the title. */
    icon?: ReactNode
    /** The card title contents. */
    title: ReactNode
    /** Optional action buttons rendered on the right side of the header. */
    actions?: ReactNode
    /** Extra classes on the underlying <Card>. */
    cardClassName?: string
    /** Override classes on the <CardHeader>. */
    headerClassName?: string
    /** Override classes on the <CardTitle>. */
    titleClassName?: string
    /** Override classes on the <CardContent>. */
    contentClassName?: string
    children: ReactNode
}

/**
 * Standardized section card used across the dashboard.
 *
 * Renders a Card with a header (emoji + title and optional action buttons on
 * the right) and a body. Existing call sites keep the same visual layout — the
 * header switches to a flex row with `justify-between` whenever `actions` are
 * provided, mirroring the previous inline markup.
 */
function SectionCard({
    icon,
    title,
    actions,
    cardClassName,
    headerClassName,
    titleClassName,
    contentClassName,
    children,
}: SectionCardProps) {
    const defaultHeaderClassName = actions
        ? 'flex flex-row items-center justify-between space-y-0 pb-2'
        : undefined

    return (
        <Card className={cardClassName}>
            {/* Teal gradient strip at top of every section card */}
            <div className="h-0.5 bg-gradient-to-r from-transparent via-accent/50 to-transparent rounded-t-xl" />
            <CardHeader className={cn(defaultHeaderClassName, headerClassName)}>
                <CardTitle className={cn(actions ? 'min-w-0' : undefined, titleClassName)}>
                    {icon != null && (
                        <span className="inline-flex items-center justify-center w-8 h-8 rounded-lg bg-accent/10 text-base shrink-0">
                            {icon}
                        </span>
                    )}
                    <span className="min-w-0 break-words">{title}</span>
                </CardTitle>
                {actions && (
                    <div className="flex items-center gap-2 shrink-0">{actions}</div>
                )}
            </CardHeader>
            <CardContent className={contentClassName}>{children}</CardContent>
        </Card>
    )
}

export default SectionCard
