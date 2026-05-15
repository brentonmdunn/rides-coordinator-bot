import { cn } from '@/lib/utils'

interface Option<T extends string> {
    value: T
    label: string
}

interface SegmentedControlProps<T extends string> {
    options: Option<T>[]
    value: T
    onChange: (value: T) => void
    disabled?: boolean
    className?: string
}

export function SegmentedControl<T extends string>({
    options,
    value,
    onChange,
    disabled = false,
    className,
}: SegmentedControlProps<T>) {
    return (
        <div
            className={cn(
                'inline-flex items-center rounded-lg bg-muted p-0.5 gap-0.5',
                className
            )}
            role="group"
        >
            {options.map((opt) => {
                const isActive = opt.value === value
                return (
                    <button
                        key={opt.value}
                        type="button"
                        role="radio"
                        aria-checked={isActive}
                        disabled={disabled}
                        onClick={() => onChange(opt.value)}
                        className={cn(
                            'px-3 py-1 text-sm font-medium rounded-md transition-all duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent',
                            isActive
                                ? 'bg-card text-foreground shadow-sm'
                                : 'text-muted-foreground hover:text-foreground',
                            disabled && 'opacity-50 cursor-not-allowed'
                        )}
                    >
                        {opt.label}
                    </button>
                )
            })}
        </div>
    )
}
