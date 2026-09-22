/**
 * phone.ts
 *
 * JS mirror of `backend/ridebot/utils/phone.py` — keep in sync with it.
 * Validates/normalizes/formats US phone numbers for the Pickup Info admin UI.
 */

export type PhoneStatus = 'ok' | 'invalid' | 'missing'

// NANP: area code and exchange can't start with 0 or 1.
const PHONE_REGEX = /^(?:\+?1[\s.-]?)?\(?([2-9]\d{2})\)?[\s.-]?([2-9]\d{2})[\s.-]?(\d{4})$/

/**
 * Return the 10 bare digits if `raw` is a valid US number, else null (also
 * null for null/blank).
 */
export function normalizePhone(raw: string | null | undefined): string | null {
    if (raw == null) return null
    const trimmed = raw.trim()
    if (!trimmed) return null

    const match = PHONE_REGEX.exec(trimmed)
    if (!match) return null

    return `${match[1]}${match[2]}${match[3]}`
}

/**
 * 10-digit stored value -> `(858) 555-1234`; any other non-blank value
 * returned trimmed as-is; null/blank -> null.
 */
export function formatPhone(stored: string | null | undefined): string | null {
    if (stored == null) return null
    const trimmed = stored.trim()
    if (!trimmed) return null

    if (/^\d{10}$/.test(trimmed)) {
        return `(${trimmed.slice(0, 3)}) ${trimmed.slice(3, 6)}-${trimmed.slice(6)}`
    }
    return trimmed
}

/** null/blank -> 'missing'; exactly 10 digits -> 'ok'; anything else -> 'invalid'. */
export function phoneStatus(stored: string | null | undefined): PhoneStatus {
    if (stored == null) return 'missing'
    const trimmed = stored.trim()
    if (!trimmed) return 'missing'
    return /^\d{10}$/.test(trimmed) ? 'ok' : 'invalid'
}

/** Client-side validity check for the form dialog — true for blank or a valid number. */
export function isValidPhoneInput(raw: string): boolean {
    const trimmed = raw.trim()
    if (!trimmed) return true
    return PHONE_REGEX.test(trimmed)
}
