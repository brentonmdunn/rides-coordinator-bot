import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "@/lib/utils"

const badgeVariants = cva(
    "inline-flex items-center text-sm font-medium transition-colors",
    {
        variants: {
            variant: {
                default: "bg-slate-100 dark:bg-zinc-800 text-slate-600 dark:text-slate-400 border border-slate-200 dark:border-zinc-700",
                success: "bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400 border border-green-200 dark:border-green-800",
                warning: "bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-400 border border-amber-200 dark:border-amber-800",
                error: "bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400 border border-red-200 dark:border-red-800",
                info: "bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400 border border-blue-200 dark:border-blue-800",
                user: "bg-slate-100 dark:bg-zinc-800 text-slate-700 dark:text-slate-300 hover:text-blue-600 dark:hover:text-blue-400 hover:underline cursor-pointer",
            },
            size: {
                sm: "px-2 py-0.5 text-xs",
                default: "px-2 py-1",
                lg: "px-3 py-1.5",
            },
            rounded: {
                default: "rounded",
                full: "rounded-full",
            },
        },
        defaultVariants: {
            variant: "default",
            size: "default",
            rounded: "default",
        },
    }
)

export interface BadgeProps
    extends React.HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {
    asButton?: boolean
}

const Badge = React.forwardRef<HTMLSpanElement, BadgeProps>(
    ({ className, variant, size, rounded, asButton, onClick, ...props }, ref) => {
        const Component = asButton || onClick ? "button" : "span"

        return (
            <Component
                ref={ref as any}
                className={cn(badgeVariants({ variant, size, rounded, className }))}
                onClick={onClick}
                type={asButton ? "button" : undefined}
                {...props}
            />
        )
    }
)
Badge.displayName = "Badge"

export { Badge, badgeVariants }
