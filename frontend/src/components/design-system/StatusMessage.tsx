import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "@/lib/utils"
import { AlertCircle, CheckCircle, Info, Loader2 } from "lucide-react"

const statusMessageVariants = cva(
    "rounded-lg p-4 flex items-start gap-3 text-sm",
    {
        variants: {
            variant: {
                loading: "bg-blue-50 dark:bg-blue-950/30 text-blue-700 dark:text-blue-300 border border-blue-200 dark:border-blue-800",
                error: "bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-400 border border-red-200 dark:border-red-800",
                success: "bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-400 border border-green-200 dark:border-green-800",
                info: "bg-blue-50 dark:bg-blue-900/20 text-blue-700 dark:text-blue-400 border border-blue-200 dark:border-blue-800",
                warning: "bg-amber-50 dark:bg-amber-900/20 text-amber-700 dark:text-amber-400 border border-amber-200 dark:border-amber-800",
            },
        },
        defaultVariants: {
            variant: "info",
        },
    }
)

const iconMap = {
    loading: Loader2,
    error: AlertCircle,
    success: CheckCircle,
    info: Info,
    warning: AlertCircle,
}

export interface StatusMessageProps
    extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof statusMessageVariants> {
    title?: string
    showIcon?: boolean
}

const StatusMessage = React.forwardRef<HTMLDivElement, StatusMessageProps>(
    ({ className, variant = "info", title, showIcon = true, children, ...props }, ref) => {
        if (!children) return null

        const Icon = variant ? iconMap[variant] : iconMap.info
        const isLoading = variant === "loading"

        return (
            <div
                ref={ref}
                className={cn(statusMessageVariants({ variant, className }))}
                role={variant === "error" ? "alert" : "status"}
                {...props}
            >
                {showIcon && (
                    <Icon
                        className={cn(
                            "h-5 w-5 shrink-0",
                            isLoading && "animate-spin"
                        )}
                    />
                )}
                <div className="flex-1">
                    {title && (
                        <div className="font-semibold mb-1">{title}</div>
                    )}
                    <div className={title ? "opacity-90" : ""}>{children}</div>
                </div>
            </div>
        )
    }
)
StatusMessage.displayName = "StatusMessage"

export { StatusMessage, statusMessageVariants }
