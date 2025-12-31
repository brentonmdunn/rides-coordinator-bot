import * as React from "react"
import { cn } from "@/lib/utils"

export interface LabelProps extends React.LabelHTMLAttributes<HTMLLabelElement> {
    required?: boolean
}

const Label = React.forwardRef<HTMLLabelElement, LabelProps>(
    ({ className, children, required, ...props }, ref) => {
        return (
            <label
                ref={ref}
                className={cn(
                    "block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2",
                    className
                )}
                {...props}
            >
                {children}
                {required && <span className="text-red-500 ml-1">*</span>}
            </label>
        )
    }
)
Label.displayName = "Label"

export { Label }
