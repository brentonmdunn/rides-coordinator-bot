import { useState, type ReactNode } from 'react'
import { ChevronDown } from 'lucide-react'
import { cn } from '@/lib/utils'

interface CollapsibleSectionProps {
    title: ReactNode
    defaultOpen?: boolean
    children: ReactNode
    className?: string
}

export function CollapsibleSection({
    title,
    defaultOpen = false,
    children,
    className,
}: CollapsibleSectionProps) {
    const [open, setOpen] = useState(defaultOpen)

    return (
        <div className={cn('rounded-xl border border-border bg-card overflow-hidden shadow-md', className)}>
            <button
                type="button"
                onClick={() => setOpen((v) => !v)}
                className="w-full flex items-center justify-between px-5 py-4 text-left hover:bg-muted/40 transition-colors"
                aria-expanded={open}
            >
                <span className="text-sm font-semibold text-muted-foreground uppercase tracking-widest">
                    {title}
                </span>
                <ChevronDown
                    className={cn(
                        'w-4 h-4 text-muted-foreground transition-transform duration-200',
                        open && 'rotate-180'
                    )}
                />
            </button>
            <div
                className={cn(
                    'transition-all duration-200 ease-in-out',
                    open ? 'opacity-100' : 'opacity-0 max-h-0 overflow-hidden pointer-events-none'
                )}
            >
                {children}
            </div>
        </div>
    )
}
