/**
 * DriverSelector.tsx
 *
 * Shared driver selector used by both the widget card view and the fullscreen
 * panel/sheet so the option to attach a `@driver` mention prefix is available
 * from anywhere in the Route Builder, not just the fullscreen view.
 */

import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from '../ui/select'

export interface DriverSelectorProps {
    drivers: string[]
    driverUsernameToName: Record<string, string>
    selectedDriver: string
    onSelectDriver: (driver: string) => void
    /** compact=true renders a smaller (h-8) trigger for overlay panels. */
    compact?: boolean
    label?: string
}

const NONE_VALUE = '__none__'

export function DriverSelector({
    drivers,
    driverUsernameToName,
    selectedDriver,
    onSelectDriver,
    compact = false,
    label = 'Driver',
}: DriverSelectorProps) {
    if (drivers.length === 0) return null

    return (
        <div>
            <div className="text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                {label}
            </div>
            <Select
                value={selectedDriver || NONE_VALUE}
                onValueChange={(v) => onSelectDriver(v === NONE_VALUE ? '' : v)}
            >
                <SelectTrigger className={compact ? 'h-8 text-sm w-full' : 'w-full'}>
                    <SelectValue />
                </SelectTrigger>
                <SelectContent>
                    <SelectItem value={NONE_VALUE}>No driver</SelectItem>
                    {drivers.map((username) => (
                        <SelectItem key={username} value={username}>
                            {driverUsernameToName[username] || `@${username}`}
                        </SelectItem>
                    ))}
                </SelectContent>
            </Select>
        </div>
    )
}
