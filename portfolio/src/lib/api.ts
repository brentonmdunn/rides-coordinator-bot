/**
 * Mock API layer for the portfolio demo.
 *
 * All GET requests return realistic in-memory fake data.
 * All mutating requests (POST / PUT / PATCH / DELETE) apply changes to the
 * in-memory store and dispatch a 'demo-action' CustomEvent so the UI can
 * show a "Demo mode" toast, then return { success: true }.
 */

// ── Exported helpers (same public API as the real lib/api.ts) ─────────────

export const API_BASE_URL = ''

export class ApiError extends Error {
    status: number
    detail: string

    constructor(status: number, detail: string) {
        super(detail)
        this.name = 'ApiError'
        this.status = status
        this.detail = detail
    }
}

export function getApiUrl(endpoint: string): string {
    return endpoint.startsWith('/') ? endpoint : `/${endpoint}`
}

// ── In-memory mutable store ────────────────────────────────────────────────

import type {
    FeatureFlag,
    AskRidesStatus,
    RideCoverage,
    PickupLocationsResponse,
    AskRidesReactionsData,
    GroupRidesResponse,
} from '../types'

interface UserAccount {
    id: number
    email: string | null
    discord_username: string | null
    discord_user_id: string | null
    role: 'admin' | 'ride_coordinator' | 'viewer'
    role_edited_by: string | null
    invited_by: string | null
    created_at: string | null
}

// ── Seed data ──────────────────────────────────────────────────────────────

let featureFlags: FeatureFlag[] = [
    { id: 1, feature: 'ask_rides_friday_enabled', enabled: true },
    { id: 2, feature: 'ask_rides_sunday_enabled', enabled: true },
    { id: 3, feature: 'ask_rides_sunday_class_enabled', enabled: false },
    { id: 4, feature: 'ride_coverage_tracking_enabled', enabled: true },
    { id: 5, feature: 'reaction_log_enabled', enabled: true },
    { id: 6, feature: 'driver_reactions_enabled', enabled: true },
    { id: 7, feature: 'group_rides_ai_enabled', enabled: true },
    { id: 8, feature: 'map_links_enabled', enabled: true },
]

let users: UserAccount[] = [
    {
        id: 1,
        email: 'demo@example.com',
        discord_username: 'bartholomew_q',
        discord_user_id: '123456789012345678',
        role: 'admin',
        role_edited_by: null,
        invited_by: null,
        created_at: '2024-09-01T08:00:00',
    },
    {
        id: 2,
        email: 'percival@ucsd.edu',
        discord_username: 'percival_thunder',
        discord_user_id: '234567890123456789',
        role: 'admin',
        role_edited_by: null,
        invited_by: null,
        created_at: '2024-09-03T10:30:00',
    },
    {
        id: 3,
        email: 'anastasia@ucsd.edu',
        discord_username: 'anastasia_w',
        discord_user_id: '345678901234567890',
        role: 'ride_coordinator',
        role_edited_by: 'bartholomew_q',
        invited_by: null,
        created_at: '2024-09-05T14:15:00',
    },
    {
        id: 4,
        email: 'cornelius@ucsd.edu',
        discord_username: 'cornelius_bee',
        discord_user_id: '456789012345678901',
        role: 'ride_coordinator',
        role_edited_by: 'bartholomew_q',
        invited_by: null,
        created_at: '2024-09-10T09:00:00',
    },
    {
        id: 5,
        email: null,
        discord_username: 'millicent_snork',
        discord_user_id: null,
        role: 'viewer',
        role_edited_by: null,
        invited_by: 'anastasia_w',
        created_at: '2024-11-12T16:45:00',
    },
    {
        id: 6,
        email: 'reginald@ucsd.edu',
        discord_username: 'reginald_fluff',
        discord_user_id: '567890123456789012',
        role: 'viewer',
        role_edited_by: null,
        invited_by: 'percival_thunder',
        created_at: '2024-10-20T11:00:00',
    },
    {
        id: 7,
        email: null,
        discord_username: 'wilhelmina_bb',
        discord_user_id: null,
        role: 'viewer',
        role_edited_by: null,
        invited_by: 'cornelius_bee',
        created_at: '2025-01-08T13:30:00',
    },
]

// ── Static mock data builders ──────────────────────────────────────────────

function makePauseStatus(
    is_paused = false,
    resume_after_date: string | null = null,
    resume_send_date: string | null = null
) {
    return { is_paused, resume_after_date, resume_send_date }
}

function getAskRidesStatus(): AskRidesStatus {
    return {
        friday: {
            enabled: featureFlags.find((f) => f.feature === 'ask_rides_friday_enabled')?.enabled ?? true,
            will_send: true,
            sent_this_week: false,
            reason: null,
            next_run: nextFriday8am(),
            last_message: {
                message_id: '1234567890123456789',
                reactions: { '🚗': 5, '✋': 12, '❌': 2 },
            },
            pause: makePauseStatus(),
        },
        sunday: {
            enabled: featureFlags.find((f) => f.feature === 'ask_rides_sunday_enabled')?.enabled ?? true,
            will_send: true,
            sent_this_week: true,
            reason: null,
            next_run: nextSunday8am(),
            last_message: {
                message_id: '9876543210987654321',
                reactions: { '🚗': 4, '✋': 9, '❌': 1 },
            },
            pause: makePauseStatus(),
        },
        sunday_class: {
            enabled: featureFlags.find((f) => f.feature === 'ask_rides_sunday_class_enabled')?.enabled ?? false,
            will_send: false,
            sent_this_week: false,
            reason: 'Feature flag disabled',
            next_run: nextSunday8am(),
            last_message: null,
            pause: makePauseStatus(),
        },
    }
}

function nextFriday8am(): string {
    const now = new Date()
    const day = now.getDay()
    const daysUntilFriday = (5 - day + 7) % 7 || 7
    const next = new Date(now)
    next.setDate(now.getDate() + daysUntilFriday)
    next.setHours(8, 0, 0, 0)
    return next.toISOString()
}

function nextSunday8am(): string {
    const now = new Date()
    const day = now.getDay()
    const daysUntilSunday = (7 - day) % 7 || 7
    const next = new Date(now)
    next.setDate(now.getDate() + daysUntilSunday)
    next.setHours(8, 0, 0, 0)
    return next.toISOString()
}

function getUpcomingDates() {
    const dates = []
    const now = new Date()
    for (let i = 0; i < 8; i++) {
        const fridayOffset = (5 - now.getDay() + 7) % 7 + i * 7
        const friday = new Date(now)
        friday.setDate(now.getDate() + fridayOffset)
        const sendDate = new Date(friday)
        sendDate.setDate(friday.getDate() - 2) // Wednesday
        dates.push({
            event_date: friday.toISOString().slice(0, 10),
            send_date: sendDate.toISOString().slice(0, 10),
            label: 'Weekly Event 1',
        })
        const sunday = new Date(friday)
        sunday.setDate(friday.getDate() + 2)
        const sundaySend = new Date(sunday)
        sundaySend.setDate(sunday.getDate() - 4) // Wednesday
        dates.push({
            event_date: sunday.toISOString().slice(0, 10),
            send_date: sundaySend.toISOString().slice(0, 10),
            label: 'Weekly Event 2',
        })
    }
    return { dates: dates.slice(0, 8), has_more: false }
}

function getPickupLocations(): PickupLocationsResponse {
    return {
        locations: [
            { key: 'sixth', value: 'Sixth loop' },
            { key: 'seventh', value: 'Seventh mail room' },
            { key: 'marshall', value: 'Marshall uppers' },
            { key: 'erc', value: 'ERC across from bamboo' },
            { key: 'muir', value: 'Muir tennis courts' },
            { key: 'eighth', value: 'Eighth basketball courts' },
            { key: 'innovation', value: 'Innovation' },
            { key: 'rita', value: 'Rita' },
            { key: 'warren_eql', value: 'Warren Equality Ln' },
            { key: 'warren_jst', value: 'Warren Justice Ln' },
            { key: 'geisel_loop', value: 'Geisel Loop' },
            { key: 'pcyn_loop', value: 'Pepper Canyon Loop' },
        ],
        map_links: {
            'Sixth loop': 'https://www.google.com/maps?q=32.881096,-117.242020',
            'Seventh mail room': 'https://www.google.com/maps?q=32.888203,-117.242347',
            'Marshall uppers': 'https://www.google.com/maps?q=32.883187,-117.241281',
            'ERC across from bamboo': 'https://www.google.com/maps?q=32.885294,-117.242357',
            'Muir tennis courts': 'https://www.google.com/maps?q=32.878133,-117.243361',
            'Eighth basketball courts': 'https://www.google.com/maps?q=32.873411,-117.242997',
            'Innovation': 'https://www.google.com/maps?q=32.879118,-117.231663',
            'Rita': 'https://www.google.com/maps?q=32.873065,-117.235532',
            'Warren Equality Ln': 'https://www.google.com/maps?q=32.883587,-117.233687',
            'Warren Justice Ln': 'https://www.google.com/maps?q=32.883156,-117.232222',
            'Geisel Loop': 'https://www.google.com/maps?q=32.881598,-117.238614',
            'Pepper Canyon Loop': 'https://www.google.com/maps?q=32.878366,-117.234230',
        },
        coordinates: {
            'Sixth loop':              { lat: 32.881096, lng: -117.242020 },
            'Seventh mail room':       { lat: 32.888203, lng: -117.242347 },
            'Marshall uppers':         { lat: 32.883187, lng: -117.241281 },
            'ERC across from bamboo':  { lat: 32.885294, lng: -117.242357 },
            'Muir tennis courts':      { lat: 32.878133, lng: -117.243361 },
            'Eighth basketball courts':{ lat: 32.873411, lng: -117.242997 },
            'Innovation':              { lat: 32.879118, lng: -117.231663 },
            'Rita':                    { lat: 32.873065, lng: -117.235532 },
            'Warren Equality Ln':      { lat: 32.883587, lng: -117.233687 },
            'Warren Justice Ln':       { lat: 32.883156, lng: -117.232222 },
            'Geisel Loop':             { lat: 32.881598, lng: -117.238614 },
            'Pepper Canyon Loop':      { lat: 32.878366, lng: -117.234230 },
        },
    }
}


function getDriverReactions(day: 'friday' | 'sunday'): AskRidesReactionsData {
    const fridayDrivers = {
        '🚗': ['bartholomew_q', 'percival_thunder', 'cornelius_bee', 'reginald_fluff', 'montgomery_wb'],
        '🔑': ['anastasia_w', 'theodora_b'],
    }
    const sundayDrivers = {
        '🚗': ['percival_thunder', 'cornelius_bee', 'leopold_w', 'gertrude_n'],
        '🔑': ['bartholomew_q'],
    }
    const reactions = day === 'friday' ? fridayDrivers : sundayDrivers
    return {
        message_type: day,
        reactions,
        username_to_name: {
            bartholomew_q: 'Bartholomew Quigglesworth',
            percival_thunder: 'Percival Thunderbottom',
            cornelius_bee: 'Cornelius Bumblebee',
            reginald_fluff: 'Reginald Fluffington',
            montgomery_wb: 'Montgomery Wobblebottom',
            anastasia_w: 'Anastasia Wobbleknee',
            theodora_b: 'Theodora Bumblesnatch',
            leopold_w: 'Leopold Whiffington',
            gertrude_n: 'Gertrude Noodlehair',
        },
        message_found: true,
    }
}

function getAskRidesReactions(type: string): AskRidesReactionsData {
    const fridayReactions = {
        '🚗': ['bartholomew_q', 'percival_thunder', 'cornelius_bee', 'reginald_fluff', 'montgomery_wb'],
        '✋': [
            'anastasia_w', 'millicent_snork', 'theodora_b', 'leopold_w',
            'clementine_p', 'wilhelmina_bb', 'gertrude_n', 'archibald_s',
            'marshall_c', 'eleanor_r', 'new_rider_1', 'new_rider_2',
        ],
        '❌': ['night_owl_99', 'busy_bee'],
    }
    const sundayReactions = {
        '🚗': ['percival_thunder', 'cornelius_bee', 'leopold_w', 'gertrude_n'],
        '✋': [
            'anastasia_w', 'millicent_snork', 'clementine_p',
            'wilhelmina_bb', 'archibald_s', 'marshall_c', 'eleanor_r', 'new_rider_3',
            'sunday_goer',
        ],
        '❌': ['night_owl_99'],
    }
    const sundayClassReactions = {
        '📖': ['theodora_b', 'leopold_w', 'clementine_p'],
        '✋': ['archibald_s', 'marshall_c'],
    }

    let reactions
    if (type === 'sunday') reactions = sundayReactions
    else if (type === 'sunday_class') reactions = sundayClassReactions
    else reactions = fridayReactions

    return {
        message_type: type,
        reactions,
        username_to_name: {
            bartholomew_q: 'Bartholomew Quigglesworth',
            percival_thunder: 'Percival Thunderbottom',
            anastasia_w: 'Anastasia Wobbleknee',
            cornelius_bee: 'Cornelius Bumblebee',
            millicent_snork: 'Millicent Snorklewhistle',
            reginald_fluff: 'Reginald Fluffington',
            wilhelmina_bb: 'Wilhelmina Bananabottom',
            montgomery_wb: 'Montgomery Wobblebottom',
            gertrude_n: 'Gertrude Noodlehair',
            archibald_s: 'Archibald Sneezeworthy',
            theodora_b: 'Theodora Bumblesnatch',
            leopold_w: 'Leopold Whiffington',
            clementine_p: 'Clementine Puddlejumper',
            marshall_c: 'Marshall Campusson',
            eleanor_r: 'Eleanor Rooseveldt',
        },
        message_found: true,
    }
}

function getRideCoverage(rideType: 'friday' | 'sunday'): RideCoverage {
    const fridayUsers = [
        { discord_username: 'anastasia_w', has_ride: true },
        { discord_username: 'millicent_snork', has_ride: true },
        { discord_username: 'theodora_b', has_ride: true },
        { discord_username: 'leopold_w', has_ride: true },
        { discord_username: 'clementine_p', has_ride: true },
        { discord_username: 'wilhelmina_bb', has_ride: true },
        { discord_username: 'gertrude_n', has_ride: true },
        { discord_username: 'archibald_s', has_ride: false },
        { discord_username: 'marshall_c', has_ride: false },
        { discord_username: 'eleanor_r', has_ride: false },
        { discord_username: 'new_rider_1', has_ride: false },
        { discord_username: 'new_rider_2', has_ride: false },
    ]
    const sundayUsers = [
        { discord_username: 'anastasia_w', has_ride: true },
        { discord_username: 'millicent_snork', has_ride: true },
        { discord_username: 'clementine_p', has_ride: true },
        { discord_username: 'wilhelmina_bb', has_ride: true },
        { discord_username: 'archibald_s', has_ride: true },
        { discord_username: 'marshall_c', has_ride: true },
        { discord_username: 'eleanor_r', has_ride: false },
        { discord_username: 'new_rider_3', has_ride: false },
        { discord_username: 'sunday_goer', has_ride: false },
    ]
    const users = rideType === 'friday' ? fridayUsers : sundayUsers
    const assigned = users.filter((u) => u.has_ride).length
    return {
        users,
        total: users.length,
        assigned,
        message_found: true,
        has_coverage_entries: true,
        is_in_visibility_window: true,
    }
}

function getGroupRidesResponse(): GroupRidesResponse {
    return {
        success: true,
        summary:
            'Total riders: 12\nDrivers: 5 (Bartholomew, Percival, Cornelius, Reginald, Montgomery)\nAll riders assigned ✓',
        groupings: [
            `🚗 **Bartholomew Quigglesworth** (4 seats)\n` +
                `  1. Anastasia Wobbleknee — Revelle College\n` +
                `  2. Millicent Snorklewhistle — Warren College\n` +
                `  3. Theodora Bumblesnatch — Sixth College\n` +
                `  4. Leopold Whiffington — Sixth College`,
            `🚗 **Percival Thunderbottom** (4 seats)\n` +
                `  1. Clementine Puddlejumper — Seventh College\n` +
                `  2. Wilhelmina Bananabottom — The Village\n` +
                `  3. Gertrude Noodlehair — Matthews Campus Apartments\n` +
                `  4. Archibald Sneezeworthy — Price Center`,
            `🚗 **Cornelius Bumblebee** (4 seats)\n` +
                `  1. Marshall Campusson — Muir College\n` +
                `  2. Eleanor Rooseveldt — Muir College\n` +
                `  3. new_rider_1 — Pepper Canyon Apartments\n` +
                `  4. new_rider_2 — Pepper Canyon Apartments`,
        ],
        error: null,
    }
}

function getReactionLog() {
    const now = new Date()
    const friday = new Date(now)
    friday.setDate(now.getDate() - ((now.getDay() + 2) % 7))
    friday.setHours(8, 15, 0, 0)

    const sunday = new Date(now)
    sunday.setDate(now.getDate() - ((now.getDay() + 0) % 7))
    sunday.setHours(8, 10, 0, 0)

    function ts(base: Date, offsetMinutes: number): string {
        const d = new Date(base.getTime() + offsetMinutes * 60000)
        return d.toISOString().replace('Z', '')
    }

    return {
        rides: [
            {
                message_id: '1234567890123456789',
                ride_type: 'friday',
                ride_date: friday.toISOString().slice(0, 10),
                label: 'Weekly Event 1',
                events: [
                    { id: 1, discord_username: 'anastasia_w', display_name: 'Anastasia Wobbleknee', emoji: '✋', action: 'add', occurred_at: ts(friday, 2) },
                    { id: 2, discord_username: 'millicent_snork', display_name: 'Millicent Snorklewhistle', emoji: '✋', action: 'add', occurred_at: ts(friday, 5) },
                    { id: 3, discord_username: 'bartholomew_q', display_name: 'Bartholomew Quigglesworth', emoji: '🚗', action: 'add', occurred_at: ts(friday, 8) },
                    { id: 4, discord_username: 'theodora_b', display_name: 'Theodora Bumblesnatch', emoji: '✋', action: 'add', occurred_at: ts(friday, 14) },
                    { id: 5, discord_username: 'percival_thunder', display_name: 'Percival Thunderbottom', emoji: '🚗', action: 'add', occurred_at: ts(friday, 21) },
                    { id: 6, discord_username: 'night_owl_99', display_name: null, emoji: '✋', action: 'add', occurred_at: ts(friday, 35) },
                    { id: 7, discord_username: 'night_owl_99', display_name: null, emoji: '✋', action: 'remove', occurred_at: ts(friday, 42) },
                    { id: 8, discord_username: 'night_owl_99', display_name: null, emoji: '❌', action: 'add', occurred_at: ts(friday, 43) },
                    { id: 9, discord_username: 'leopold_w', display_name: 'Leopold Whiffington', emoji: '✋', action: 'add', occurred_at: ts(friday, 67) },
                    { id: 10, discord_username: 'clementine_p', display_name: 'Clementine Puddlejumper', emoji: '✋', action: 'add', occurred_at: ts(friday, 95) },
                    { id: 11, discord_username: 'cornelius_bee', display_name: 'Cornelius Bumblebee', emoji: '🚗', action: 'add', occurred_at: ts(friday, 112) },
                    { id: 12, discord_username: 'wilhelmina_bb', display_name: 'Wilhelmina Bananabottom', emoji: '✋', action: 'add', occurred_at: ts(friday, 140) },
                    { id: 13, discord_username: 'gertrude_n', display_name: 'Gertrude Noodlehair', emoji: '✋', action: 'add', occurred_at: ts(friday, 180) },
                    { id: 14, discord_username: 'reginald_fluff', display_name: 'Reginald Fluffington', emoji: '🚗', action: 'add', occurred_at: ts(friday, 210) },
                    { id: 15, discord_username: 'archibald_s', display_name: 'Archibald Sneezeworthy', emoji: '✋', action: 'add', occurred_at: ts(friday, 255) },
                ],
            },
            {
                message_id: '9876543210987654321',
                ride_type: 'sunday',
                ride_date: sunday.toISOString().slice(0, 10),
                label: 'Weekly Event 2',
                events: [
                    { id: 16, discord_username: 'percival_thunder', display_name: 'Percival Thunderbottom', emoji: '🚗', action: 'add', occurred_at: ts(sunday, 3) },
                    { id: 17, discord_username: 'anastasia_w', display_name: 'Anastasia Wobbleknee', emoji: '✋', action: 'add', occurred_at: ts(sunday, 9) },
                    { id: 18, discord_username: 'millicent_snork', display_name: 'Millicent Snorklewhistle', emoji: '✋', action: 'add', occurred_at: ts(sunday, 17) },
                    { id: 19, discord_username: 'cornelius_bee', display_name: 'Cornelius Bumblebee', emoji: '🚗', action: 'add', occurred_at: ts(sunday, 25) },
                    { id: 20, discord_username: 'clementine_p', display_name: 'Clementine Puddlejumper', emoji: '✋', action: 'add', occurred_at: ts(sunday, 38) },
                    { id: 21, discord_username: 'leopold_w', display_name: 'Leopold Whiffington', emoji: '🚗', action: 'add', occurred_at: ts(sunday, 52) },
                    { id: 22, discord_username: 'wilhelmina_bb', display_name: 'Wilhelmina Bananabottom', emoji: '✋', action: 'add', occurred_at: ts(sunday, 71) },
                    { id: 23, discord_username: 'archibald_s', display_name: 'Archibald Sneezeworthy', emoji: '✋', action: 'add', occurred_at: ts(sunday, 90) },
                    { id: 24, discord_username: 'marshall_c', display_name: 'Marshall Campusson', emoji: '✋', action: 'add', occurred_at: ts(sunday, 115) },
                    { id: 25, discord_username: 'sunday_goer', display_name: null, emoji: '✋', action: 'add', occurred_at: ts(sunday, 143) },
                    { id: 26, discord_username: 'gertrude_n', display_name: 'Gertrude Noodlehair', emoji: '🚗', action: 'add', occurred_at: ts(sunday, 160) },
                    { id: 27, discord_username: 'night_owl_99', display_name: null, emoji: '❌', action: 'add', occurred_at: ts(sunday, 200) },
                    { id: 28, discord_username: 'eleanor_r', display_name: 'Eleanor Rooseveldt', emoji: '✋', action: 'add', occurred_at: ts(sunday, 240) },
                ],
            },
        ],
    }
}

// ── Route matcher ──────────────────────────────────────────────────────────

function getMockData(endpoint: string): unknown {
    // Strip query string for matching
    const path = endpoint.split('?')[0]

    // GET /api/me
    if (path === '/api/me') {
        return { email: 'demo@example.com', role: 'admin', is_local: false }
    }

    // GET /api/pickup-locations
    if (path === '/api/pickup-locations') {
        return getPickupLocations()
    }

    // GET /api/check-pickups/friday or /api/check-pickups/sunday
    if (path === '/api/check-pickups/friday') {
        return getRideCoverage('friday')
    }
    if (path === '/api/check-pickups/sunday') {
        return getRideCoverage('sunday')
    }

    // GET /api/check-pickups/driver-reactions/:day
    if (path.startsWith('/api/check-pickups/driver-reactions/')) {
        const day = path.split('/api/check-pickups/driver-reactions/')[1] as 'friday' | 'sunday'
        return getDriverReactions(day)
    }

    // GET /api/check-pickups (with ride type in query or body — not used here, fallback)
    if (path.startsWith('/api/check-pickups')) {
        return getRideCoverage('friday')
    }

    // GET /api/ask-rides/status
    if (path === '/api/ask-rides/status') {
        return getAskRidesStatus()
    }

    // GET /api/ask-rides/upcoming-dates (with optional /:jobName suffix)
    if (path.startsWith('/api/ask-rides/upcoming-dates')) {
        return getUpcomingDates()
    }

    // GET /api/ask-rides/reactions/:type
    if (path.startsWith('/api/ask-rides/reactions/')) {
        const type = path.split('/api/ask-rides/reactions/')[1]
        return getAskRidesReactions(type)
    }

    // GET /api/driver-reactions (generic fallback)
    if (path === '/api/driver-reactions') {
        return getDriverReactions('friday')
    }

    // GET /api/reaction-details (generic fallback)
    if (path === '/api/reaction-details') {
        return getAskRidesReactions('friday')
    }

    // GET /api/ride-coverage
    if (path === '/api/ride-coverage') {
        return getRideCoverage('friday')
    }

    // GET /api/feature-flags
    if (path === '/api/feature-flags') {
        return { flags: featureFlags }
    }

    // GET /api/admin/users
    if (path === '/api/admin/users') {
        return {
            users,
            current_user_email: 'demo@example.com',
            admin_emails: ['demo@example.com', 'percival@ucsd.edu'],
        }
    }

    // GET /api/map-links (same as pickup-locations for map tab)
    if (path === '/api/map-links') {
        return getPickupLocations()
    }

    // GET /api/reaction-log
    if (path === '/api/reaction-log') {
        return getReactionLog()
    }

    // GET /api/reaction-log/stream — handled separately (never returns data via GET)
    if (path === '/api/reaction-log/stream') {
        return {}
    }

    // GET /api/usernames (used by GroupRides mention autocomplete)
    if (path === '/api/usernames') {
        return {
            usernames: users
                .filter((u) => u.discord_username)
                .map((u) => u.discord_username),
        }
    }

    return {}
}

// ── In-memory mutation handler ─────────────────────────────────────────────

function applyMutation(endpoint: string, method: string, body: unknown): unknown {
    const path = endpoint.split('?')[0]

    // POST /api/list-pickups — return fake LocationData
    if (path === '/api/list-pickups' && method === 'POST') {
        const locationData = {
            housing_groups: {
                'On Campus': {
                    emoji: '🏫',
                    count: 7,
                    locations: {
                        'Revelle College': [
                            { name: 'Bartholomew Quigglesworth', discord_username: 'bartholomew_q' },
                            { name: 'Anastasia Wobbleknee', discord_username: 'anastasia_w' },
                        ],
                        'Warren College': [
                            { name: 'Cornelius Bumblebee', discord_username: 'cornelius_bee' },
                            { name: 'Millicent Snorklewhistle', discord_username: 'millicent_snork' },
                        ],
                        'Sixth College': [
                            { name: 'Theodora Bumblesnatch', discord_username: 'theodora_b' },
                            { name: 'Leopold Whiffington', discord_username: 'leopold_w' },
                        ],
                        'Seventh College': [
                            { name: 'Clementine Puddlejumper', discord_username: 'clementine_p' },
                        ],
                    },
                },
                'Apartments': {
                    emoji: '🏠',
                    count: 5,
                    locations: {
                        'Pepper Canyon Apartments': [
                            { name: 'Percival Thunderbottom', discord_username: 'percival_thunder' },
                            { name: 'Reginald Fluffington', discord_username: 'reginald_fluff' },
                        ],
                        'The Village': [
                            { name: 'Wilhelmina Bananabottom', discord_username: 'wilhelmina_bb' },
                            { name: 'Montgomery Wobblebottom', discord_username: 'montgomery_wb' },
                        ],
                        'Matthews Campus Apartments': [
                            { name: 'Gertrude Noodlehair', discord_username: 'gertrude_n' },
                        ],
                    },
                },
            },
            unknown_users: ['new_rider_1', 'mystery_rider'],
        }
        return { success: true, data: locationData }
    }

    // POST /api/make-route — return a fake formatted route
    if (path === '/api/make-route' && method === 'POST') {
        const payload = body as { locations?: string[]; leave_time?: string } | null
        const locations = payload?.locations ?? ['Sixth loop', 'Marshall uppers', 'Muir tennis courts']
        const leaveTime = payload?.leave_time ?? '6:40pm'
        const stops = locations.map((loc, i) => `${i + 1}. ${loc}`).join('\n')
        return {
            success: true,
            route: `🚗 Route — Leave ${leaveTime}\n\n${stops}\n\n📍 Destination: Church`,
        }
    }

    // POST /api/group-rides — return a plausible grouping
    if (path === '/api/group-rides' && method === 'POST') {
        return getGroupRidesResponse()
    }

    // PUT /api/feature-flags/:flagName
    if (path.startsWith('/api/feature-flags/') && method === 'PUT') {
        const flagName = decodeURIComponent(path.split('/api/feature-flags/')[1])
        const payload = body as { enabled?: boolean } | null
        if (payload && typeof payload.enabled === 'boolean') {
            featureFlags = featureFlags.map((f) =>
                f.feature === flagName ? { ...f, enabled: payload.enabled! } : f
            )
        }
        return { success: true }
    }

    // PUT /api/admin/users/:email/role
    if (path.includes('/api/admin/users/') && path.endsWith('/role') && method === 'PUT') {
        const segments = path.split('/')
        const email = decodeURIComponent(segments[segments.length - 2])
        const payload = body as { role?: string } | null
        if (payload?.role) {
            users = users.map((u) =>
                u.email === email
                    ? { ...u, role: payload.role as UserAccount['role'], role_edited_by: 'demo@example.com' }
                    : u
            )
        }
        return { success: true }
    }

    // POST /api/admin/users/invite
    if (path === '/api/admin/users/invite' && method === 'POST') {
        const payload = body as { discord_username?: string; role?: string } | null
        if (payload?.discord_username) {
            const newId = Math.max(...users.map((u) => u.id)) + 1
            users = [
                ...users,
                {
                    id: newId,
                    email: null,
                    discord_username: payload.discord_username,
                    discord_user_id: null,
                    role: (payload.role ?? 'viewer') as UserAccount['role'],
                    role_edited_by: null,
                    invited_by: 'demo@example.com',
                    created_at: new Date().toISOString(),
                },
            ]
        }
        return { success: true }
    }

    // DELETE /api/admin/users/:id
    if (path.startsWith('/api/admin/users/') && method === 'DELETE') {
        const idStr = path.split('/api/admin/users/')[1]
        const id = parseInt(idStr, 10)
        if (!isNaN(id)) {
            users = users.filter((u) => u.id !== id)
        }
        return { success: true }
    }

    // POST /api/ask-rides/pause/:jobName or /api/ask-rides/resume/:jobName
    // (no persistent state needed — the GET /status already returns live featureFlags)

    return { success: true }
}

// ── Main exported fetch function ───────────────────────────────────────────

const MUTATING_METHODS = new Set(['POST', 'PUT', 'PATCH', 'DELETE'])

export async function apiFetch(endpoint: string, options?: RequestInit): Promise<Response> {
    const method = (options?.method ?? 'GET').toUpperCase()

    // Add a small artificial delay to make it feel like a real network call
    await new Promise((resolve) => setTimeout(resolve, 120 + Math.random() * 180))

    if (MUTATING_METHODS.has(method)) {
        // Fire demo-action event so the UI can show a toast
        window.dispatchEvent(
            new CustomEvent('demo-action', {
                detail: { message: 'Demo mode: no real changes were made.' },
            })
        )

        // Parse body if present so mutations can inspect it
        let parsedBody: unknown = null
        if (options?.body && typeof options.body === 'string') {
            try {
                parsedBody = JSON.parse(options.body)
            } catch {
                // ignore
            }
        }

        const result = applyMutation(endpoint, method, parsedBody)
        return new Response(JSON.stringify(result), {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
        })
    }

    const data = getMockData(endpoint)
    return new Response(JSON.stringify(data), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
    })
}
