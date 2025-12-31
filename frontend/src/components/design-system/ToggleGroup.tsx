import * as React from "react"
import { cn } from "@/lib/utils"

interface ToggleGroupContextValue {
    value?: string
    onChange?: (value: string) => void
    disabled?: boolean
}

const ToggleGroupContext = React.createContext<ToggleGroupContextValue>({})

export interface ToggleGroupProps extends Omit<React.HTMLAttributes<HTMLDivElement>, 'onChange'> {
    value?: string
    onChange?: (value: string) => void
    disabled?: boolean
}

const ToggleGroup = React.forwardRef<HTMLDivElement, ToggleGroupProps>(
    ({ className, value, onChange, disabled, children, ...props }, ref) => {
        return (
            <ToggleGroupContext.Provider value={{ value, onChange, disabled }}>
                <div
                    ref={ref}
                    className={cn("flex gap-2", className)}
                    role="group"
                    {...props}
                >
                    {children}
                </div>
            </ToggleGroupContext.Provider>
        )
    }
)
ToggleGroup.displayName = "ToggleGroup"

export interface ToggleGroupItemProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
    value: string
}

const ToggleGroupItem = React.forwardRef<HTMLButtonElement, ToggleGroupItemProps>(
    ({ className, value: itemValue, children, disabled: itemDisabled, ...props }, ref) => {
        const { value, onChange, disabled: groupDisabled } = React.useContext(ToggleGroupContext)
        const isSelected = value === itemValue
        const isDisabled = itemDisabled || groupDisabled

        return (
            <button
                ref={ref}
                type="button"
                disabled={isDisabled}
                onClick={() => onChange?.(itemValue)}
                className={cn(
                    "flex-1 px-4 py-2.5 text-base font-semibold rounded-md border transition-all",
                    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
                    "disabled:opacity-50 disabled:cursor-not-allowed",
                    isSelected
                        ? "bg-primary text-primary-foreground border-primary shadow-sm"
                        : "bg-background border-input hover:bg-accent hover:text-accent-foreground",
                    className
                )}
                aria-pressed={isSelected}
                {...props}
            >
                {children}
            </button>
        )
    }
)
ToggleGroupItem.displayName = "ToggleGroupItem"

export { ToggleGroup, ToggleGroupItem }
