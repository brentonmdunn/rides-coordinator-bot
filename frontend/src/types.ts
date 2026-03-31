/**
 * Represents a group of pickup locations logically tied together (e.g. by campus area).
 */
export interface HousingGroup {
    /** Emoji to represent the group visually */
    emoji: string
    /** Total number of people awaiting pickup in this group */
    count: number
    /** Dictionary mapping a specific location string to the list of people there */
    locations: {
        [location: string]: Array<{
            name: string
            discord_username: string | null
        }>
    }
}

/**
 * Response structure when fetching all pickup locations for a ride event.
 */
export interface LocationData {
    /** Housing groups keyed by an identifier (e.g. "Scholars", "Off Campus") */
    housing_groups: {
        [groupName: string]: HousingGroup
    }
    /** List of discord usernames whose locations are unknown */
    unknown_users: string[]
}

/**
 * Represents a boolean configuration toggle downloaded from the backend.
 */
export interface FeatureFlag {
    id: number
    feature: string
    enabled: boolean
}

export interface AskRidesJobStatus {
    enabled: boolean
    will_send: boolean
    sent_this_week?: boolean
    reason: string | null
    next_run: string
    last_message?: {
        message_id: string
        reactions: { [emoji: string]: number }
    } | null
    pause: PauseStatus
}

export interface PauseStatus {
    is_paused: boolean
    resume_after_date: string | null
    resume_send_date: string | null
}

export interface UpcomingDate {
    event_date: string
    send_date: string
    label: string
}

export interface AskRidesStatus {
    friday: AskRidesJobStatus
    sunday: AskRidesJobStatus
    sunday_class: AskRidesJobStatus
}

export interface GroupRidesResponse {
    success: boolean
    summary: string | null
    groupings: string[] | null
    error: string | null
}

export interface RideCoverageUser {
    discord_username: string
    has_ride: boolean
}

export interface RideCoverage {
    users: RideCoverageUser[]
    total: number
    assigned: number
    message_found: boolean
    has_coverage_entries: boolean
}

export interface PickupLocation {
    key: string
    value: string
}

export interface PickupLocationsResponse {
    locations: PickupLocation[]
    map_links: { [location: string]: string }
    coordinates: { [location: string]: { lat: number; lng: number } }
}

export interface MakeRouteResponse {
    success: boolean
    route: string | null
    error: string | null
}

export interface AskRidesReactionsData {
    message_type: string
    reactions: Record<string, string[]>
    username_to_name: Record<string, string>
    message_found: boolean
}

/**
 * Represents the access tier of the authenticated user.
 */
export type AccountRole = 'admin' | 'ride_coordinator' | 'viewer'

export interface UserPreferences {
    show_map_labels: boolean
}
