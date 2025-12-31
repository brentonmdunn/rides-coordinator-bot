import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "@/lib/utils"

const sectionVariants = cva(
    "rounded-lg border transition-colors",
    {
        variants: {
            variant: {
                default: "bg-white dark:bg-zinc-900 border-slate-200 dark:border-zinc-700",
                muted: "bg-slate-50 dark:bg-zinc-800/50 border-slate-100 dark:border-zinc-700",
                warning: "bg-amber-50 dark:bg-amber-950/30 border-amber-200 dark:border-amber-800",
                success: "bg-emerald-50 dark:bg-emerald-950/20 border-emerald-100 dark:border-emerald-900/50",
                info: "bg-blue-50 dark:bg-blue-900/20 border-blue-200 dark:border-blue-800",
                error: "bg-red-50 dark:bg-red-900/20 border-red-200 dark:border-red-800",
            },
            padding: {
                none: "",
                sm: "p-3",
                default: "p-4",
                lg: "p-6",
            },
        },
        defaultVariants: {
            variant: "muted",
            padding: "default",
        },
    }
)

export interface SectionProps
    extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof sectionVariants> { }

const Section = React.forwardRef<HTMLDivElement, SectionProps>(
    ({ className, variant, padding, ...props }, ref) => {
        return (
            <div
                ref={ref}
                className={cn(sectionVariants({ variant, padding, className }))}
                {...props}
            />
        )
    }
)
Section.displayName = "Section"

export { Section, sectionVariants }
