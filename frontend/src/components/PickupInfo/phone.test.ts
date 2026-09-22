import { describe, expect, it } from 'vitest'
import { formatPhone, isValidPhoneInput, normalizePhone, phoneStatus } from './phone'

describe('normalizePhone', () => {
    it('accepts a plain 10-digit number', () => {
        expect(normalizePhone('8585551234')).toBe('8585551234')
    })

    it.each([
        '858-555-1234',
        '(858) 555-1234',
        '858.555.1234',
        '858 555 1234',
        '+1 858 555 1234',
        '1-858-555-1234',
        '+18585551234',
    ])('accepts %s', (raw) => {
        expect(normalizePhone(raw)).toBe('8585551234')
    })

    it('returns null for null/blank input', () => {
        expect(normalizePhone(null)).toBeNull()
        expect(normalizePhone(undefined)).toBeNull()
        expect(normalizePhone('')).toBeNull()
        expect(normalizePhone('   ')).toBeNull()
    })

    it('returns null for area codes/exchanges starting with 0 or 1', () => {
        expect(normalizePhone('158-555-1234')).toBeNull()
        expect(normalizePhone('858-155-1234')).toBeNull()
    })

    it('returns null for garbage input', () => {
        expect(normalizePhone('not a phone number')).toBeNull()
        expect(normalizePhone('12345')).toBeNull()
    })
})

describe('formatPhone', () => {
    it('formats a 10-digit stored value', () => {
        expect(formatPhone('8585551234')).toBe('(858) 555-1234')
    })

    it('returns other non-blank values trimmed as-is', () => {
        expect(formatPhone('  not a number  ')).toBe('not a number')
    })

    it('returns null for null/blank', () => {
        expect(formatPhone(null)).toBeNull()
        expect(formatPhone(undefined)).toBeNull()
        expect(formatPhone('')).toBeNull()
        expect(formatPhone('   ')).toBeNull()
    })
})

describe('phoneStatus', () => {
    it('is missing for null/blank', () => {
        expect(phoneStatus(null)).toBe('missing')
        expect(phoneStatus(undefined)).toBe('missing')
        expect(phoneStatus('')).toBe('missing')
    })

    it('is ok for exactly 10 digits', () => {
        expect(phoneStatus('8585551234')).toBe('ok')
    })

    it('is invalid for anything else', () => {
        expect(phoneStatus('not a phone number')).toBe('invalid')
        expect(phoneStatus('12345')).toBe('invalid')
    })
})

describe('isValidPhoneInput', () => {
    it('is valid for blank input', () => {
        expect(isValidPhoneInput('')).toBe(true)
        expect(isValidPhoneInput('   ')).toBe(true)
    })

    it('is valid for any accepted format', () => {
        expect(isValidPhoneInput('(858) 555-1234')).toBe(true)
        expect(isValidPhoneInput('+1 858 555 1234')).toBe(true)
    })

    it('is invalid for garbage input', () => {
        expect(isValidPhoneInput('not a phone number')).toBe(false)
    })
})
