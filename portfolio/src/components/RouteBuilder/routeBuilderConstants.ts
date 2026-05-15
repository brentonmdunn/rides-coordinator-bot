export const PRESET_TIMES = [
    { key: 'friday', label: 'Friday Fellowship', shortLabel: 'Fri (7:10pm)', time: '7:10pm' },
    { key: 'sunday', label: 'Sunday Service', shortLabel: 'Sun (10:10am)', time: '10:10am' },
    { key: 'sunday_class', label: 'Sunday Class', shortLabel: 'Class (8:40am)', time: '8:40am' },
    { key: 'discipleship', label: 'Discipleship', shortLabel: 'Disc (7:10am)', time: '7:10am' },
    { key: 'custom', label: 'Custom', shortLabel: 'Custom', time: '' },
] as const

export type TimeModeKey = typeof PRESET_TIMES[number]['key']

/** Map from key → default time string (empty string for 'custom'). */
export const PRESET_TIME_MAP: Record<TimeModeKey, string> = Object.fromEntries(
    PRESET_TIMES.map((p) => [p.key, p.time])
) as Record<TimeModeKey, string>
