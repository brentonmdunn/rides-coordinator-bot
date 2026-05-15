import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'

interface LabeledFieldProps {
    label: ReactNode
    /** Helper text rendered below the field. */
    hint?: ReactNode
    className?: string
    children: ReactNode
}

/**
 * Consistent labeled-field wrapper used across the dashboard forms.
 *
 * Renders the standard `<label class="block">` + `<span>` title + child input
 * pattern, optionally followed by a small hint paragraph.
 */
function LabeledField({ label, hint, className, children }: LabeledFieldProps) {
    return (
        <label className={cn('block', className)}>
            <span className="text-sm font-medium text-foreground mb-2 block">
                {label}
            </span>
            {children}
            {hint != null && (
                <p className="text-xs text-muted-foreground mt-1">{hint}</p>
            )}
        </label>
    )
}

export default LabeledField
