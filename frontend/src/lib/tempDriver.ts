/**
 * tempDriver.ts
 *
 * Pure helpers for the "Temporary" driver flow in RoleManagement: the
 * preset -> duration-string mapping, the date-input bounds (today..today+90),
 * and the date formatting used by the expiry badge, its tooltip, and the
 * "removed automatically at ..." helper text.
 *
 * These are intentionally free of React/Discord/API concerns so they can be
 * unit tested directly.
 */

export interface DurationPreset {
    label: string
    value: string
}

/** Order matters — this is the order the chips render in. */
export const DURATION_PRESETS: DurationPreset[] = [
    { label: '3 days', value: '3d' },
    { label: '1 week', value: '1w' },
    { label: '2 weeks', value: '2w' },
    { label: '1 month', value: '30d' },
]

export const DEFAULT_DURATION_PRESET = '1w'

export const TEMP_DRIVER_MAX_DAYS = 90

const CUSTOM_DATE_RE = /^\d{4}-\d{2}-\d{2}$/
const PRESET_RE = /^(\d+)(d|w)$/

/** True for a `YYYY-MM-DD` string, as sent by the custom date input. */
export function isCustomDateValue(value: string): boolean {
    return CUSTOM_DATE_RE.test(value)
}

/** Days represented by a preset value (e.g. `"2w"` -> 14), or null if not a preset. */
export function presetToDays(value: string): number | null {
    const match = PRESET_RE.exec(value)
    if (!match) return null
    const amount = Number(match[1])
    return match[2] === 'w' ? amount * 7 : amount
}

function pad2(n: number): string {
    return String(n).padStart(2, '0')
}

/** Formats a local `Date` as `YYYY-MM-DD` (the shape the date input and API expect). */
export function toDateInputValue(date: Date): string {
    return `${date.getFullYear()}-${pad2(date.getMonth() + 1)}-${pad2(date.getDate())}`
}

/** A new `Date` `days` days after `date` (local time, no mutation of the input). */
export function addDays(date: Date, days: number): Date {
    const result = new Date(date)
    result.setDate(result.getDate() + days)
    return result
}

/**
 * The `min`/`max` values for the custom date `<input type="date">`:
 * today through today + {@link TEMP_DRIVER_MAX_DAYS} days, both local.
 */
export function getDateInputBounds(now: Date = new Date()): { min: string; max: string } {
    return {
        min: toDateInputValue(now),
        max: toDateInputValue(addDays(now, TEMP_DRIVER_MAX_DAYS)),
    }
}

/** Parses a `YYYY-MM-DD` string into a local `Date` at midnight (avoids UTC-shift bugs). */
function parseDateInputValue(value: string): Date {
    const [year, month, day] = value.split('-').map(Number)
    return new Date(year, month - 1, day)
}

/** Formats a `YYYY-MM-DD` string or an ISO datetime string as `Mon D` (e.g. `Oct 5`). */
export function formatMonthDay(value: string): string {
    const date = isCustomDateValue(value) ? parseDateInputValue(value) : new Date(value)
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

/** Formats an ISO datetime string as a full local date + time, for tooltips. */
export function formatFullDateTime(isoString: string): string {
    const date = new Date(isoString)
    return date.toLocaleString('en-US', {
        weekday: 'short',
        month: 'short',
        day: 'numeric',
        year: 'numeric',
        hour: 'numeric',
        minute: '2-digit',
    })
}

/** The badge label for a temp row, e.g. `Temp · expires Oct 5`. */
export function formatExpiryBadge(isoString: string): string {
    return `Temp · expires ${formatMonthDay(isoString)}`
}

/**
 * Resolves what the add/edit control's `duration` value (a preset code or a
 * `YYYY-MM-DD` custom date) will expire on, for the "Removed automatically
 * at 11:59 PM on {date}" helper text. Returns null if `duration` is neither.
 */
export function resolveHelperDateLabel(duration: string, now: Date = new Date()): string | null {
    if (isCustomDateValue(duration)) {
        return formatMonthDay(duration)
    }
    const days = presetToDays(duration)
    if (days === null) return null
    return formatMonthDay(toDateInputValue(addDays(now, days)))
}
