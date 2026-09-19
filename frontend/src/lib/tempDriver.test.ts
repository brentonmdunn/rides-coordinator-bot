import { describe, expect, it } from 'vitest'
import {
    DEFAULT_DURATION_PRESET,
    DURATION_PRESETS,
    TEMP_DRIVER_MAX_DAYS,
    addDays,
    formatExpiryBadge,
    formatFullDateTime,
    formatMonthDay,
    getDateInputBounds,
    isCustomDateValue,
    presetToDays,
    resolveHelperDateLabel,
    toDateInputValue,
} from './tempDriver'

describe('DURATION_PRESETS', () => {
    it('has the four presets in order, with 1 week as the default', () => {
        expect(DURATION_PRESETS.map((p) => p.value)).toEqual(['3d', '1w', '2w', '30d'])
        expect(DURATION_PRESETS.map((p) => p.label)).toEqual([
            '3 days',
            '1 week',
            '2 weeks',
            '1 month',
        ])
        expect(DEFAULT_DURATION_PRESET).toBe('1w')
    })
})

describe('isCustomDateValue', () => {
    it('matches YYYY-MM-DD only', () => {
        expect(isCustomDateValue('2026-10-05')).toBe(true)
        expect(isCustomDateValue('1w')).toBe(false)
        expect(isCustomDateValue('3d')).toBe(false)
        expect(isCustomDateValue('10/5/2026')).toBe(false)
    })
})

describe('presetToDays', () => {
    it('converts each preset to days', () => {
        expect(presetToDays('3d')).toBe(3)
        expect(presetToDays('1w')).toBe(7)
        expect(presetToDays('2w')).toBe(14)
        expect(presetToDays('30d')).toBe(30)
    })

    it('returns null for non-preset values', () => {
        expect(presetToDays('2026-10-05')).toBeNull()
        expect(presetToDays('garbage')).toBeNull()
    })
})

describe('toDateInputValue / addDays', () => {
    it('formats a local date as YYYY-MM-DD, zero-padded', () => {
        expect(toDateInputValue(new Date(2026, 0, 5))).toBe('2026-01-05')
        expect(toDateInputValue(new Date(2026, 10, 30))).toBe('2026-11-30')
    })

    it('adds days without mutating the input', () => {
        const start = new Date(2026, 0, 30)
        const result = addDays(start, 5)
        expect(toDateInputValue(result)).toBe('2026-02-04')
        expect(toDateInputValue(start)).toBe('2026-01-30')
    })
})

describe('getDateInputBounds', () => {
    it('returns today as min and today+90 as max', () => {
        const now = new Date(2026, 0, 1)
        const { min, max } = getDateInputBounds(now)
        expect(min).toBe('2026-01-01')
        expect(max).toBe(toDateInputValue(addDays(now, TEMP_DRIVER_MAX_DAYS)))
        expect(max).toBe('2026-04-01')
    })
})

describe('formatMonthDay', () => {
    it('formats a YYYY-MM-DD custom date', () => {
        expect(formatMonthDay('2026-10-05')).toBe('Oct 5')
    })

    it('formats an ISO datetime string', () => {
        expect(formatMonthDay('2026-10-05T23:59:59-07:00')).toBe('Oct 5')
    })
})

describe('formatFullDateTime', () => {
    it('formats an ISO datetime as a full local date and time', () => {
        const result = formatFullDateTime('2026-10-05T23:59:59-07:00')
        expect(result).toContain('2026')
        expect(result).toContain('Oct')
        expect(result).toMatch(/\d{1,2}:\d{2}/)
    })
})

describe('formatExpiryBadge', () => {
    it('renders the badge label', () => {
        expect(formatExpiryBadge('2026-10-05T23:59:59-07:00')).toBe('Temp · expires Oct 5')
    })
})

describe('resolveHelperDateLabel', () => {
    const now = new Date(2026, 0, 1)

    it('resolves a preset relative to now', () => {
        expect(resolveHelperDateLabel('3d', now)).toBe('Jan 4')
        expect(resolveHelperDateLabel('1w', now)).toBe('Jan 8')
        expect(resolveHelperDateLabel('2w', now)).toBe('Jan 15')
        expect(resolveHelperDateLabel('30d', now)).toBe('Jan 31')
    })

    it('resolves a custom date directly', () => {
        expect(resolveHelperDateLabel('2026-12-25', now)).toBe('Dec 25')
    })

    it('returns null for garbage input', () => {
        expect(resolveHelperDateLabel('nonsense', now)).toBeNull()
    })
})
