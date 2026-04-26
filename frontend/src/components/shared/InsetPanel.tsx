import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'

interface InsetPanelProps {
    /** When true, the panel mounts with the existing fade/slide-in animation. */
    animated?: boolean
    className?: string
    children: ReactNode
}

/**
 * Subtle inset panel (`p-4 bg-muted/50 rounded-lg border border-border`) used
 * to visually nest secondary form fields within a section card.
 */
function InsetPanel({ animated = false, className, children }: InsetPanelProps) {
    return (
        <div
            className={cn(
                'p-4 bg-muted/50 rounded-lg border border-border',
                animated && 'animate-in fade-in slide-in-from-top-2',
                className,
            )}
        >
            {children}
        </div>
    )
}

export default InsetPanel
