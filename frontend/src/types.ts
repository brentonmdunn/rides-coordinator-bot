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
            drive_back: boolean
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
    wednesday: AskRidesJobStatus
    friday: AskRidesJobStatus
    sunday: AskRidesJobStatus
    sunday_class: AskRidesJobStatus
}

export type FellowshipSeason = 'friday' | 'wednesday'

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
    is_in_visibility_window: boolean
}

// Raw shape of GET /api/map-locations (ungated read endpoint).
export interface MapLocation {
    name: string
    latitude: number
    longitude: number
    map_url: string
}

export interface MapLocationsResponse {
    locations: MapLocation[]
}

export interface PickupLocation {
    key: string
    value: string
}

// Client-side adapter shape derived from MapLocationsResponse (key === value === name);
// kept so RouteBuilder internals and useRouteGeometry stay unchanged.
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
    /** Names of non-Discord riders tagged with each emoji, for the day */
    non_discord?: Record<string, string[]>
    message_found: boolean
}

/**
 * Represents the access tier of the authenticated user.
 */
export type AccountRole = 'admin' | 'ride_coordinator' | 'viewer'

export interface UserPreferences {
    show_map_labels: boolean
}

/**
 * Identifiers for the four editable ask-rides Discord messages. Matches the
 * backend `AskRidesMessageType` StrEnum values.
 */
export type AskRidesMessageType =
    | 'wednesday_fellowship'
    | 'friday_fellowship'
    | 'sunday_service'
    | 'sunday_class'

/**
 * A title/body/color template — either the currently-effective (possibly
 * customized) version, or the pristine hardcoded default.
 */
export interface AskRidesMessageContent {
    title: string
    body: string
    color: string
}

/**
 * The effective template for one message type, as returned by
 * `GET /api/ask-rides/messages` and by the PUT/DELETE mutation responses.
 */
export interface AskRidesMessageTemplate extends AskRidesMessageContent {
    is_customized: boolean
    default: AskRidesMessageContent
}

/**
 * Response envelope for `GET /api/ask-rides/messages`.
 */
export interface AskRidesMessagesResponse {
    templates: Record<AskRidesMessageType, AskRidesMessageTemplate>
    allowed_colors: string[]
    allowed_placeholders: Record<AskRidesMessageType, string[]>
}

/**
 * Response for `GET /api/ask-rides/coordinator` and the body/response shape
 * for `PUT /api/ask-rides/coordinator`.
 */
export interface AskRidesCoordinator {
    user_id: string | null
    configured: boolean
    username?: string
    /** Only present on GET when the bot could resolve the user. */
    display_name?: string
    warning?: string
}

/**
 * Identifiers for the two independently-schedulable ask-rides send slots.
 * Matches the backend `AskRidesScheduleSlot` StrEnum values.
 */
export type AskRidesScheduleSlot = 'wednesday_reminder' | 'fri_sun_group'

/**
 * The effective day/time for one schedule slot, as returned by
 * `GET /api/ask-rides/schedule` and by the PUT/DELETE mutation responses.
 * `day_of_week` is 0=Monday .. 6=Sunday.
 */
export interface AskRidesScheduleEntry {
    day_of_week: number
    hour: number
    minute: number
    is_customized: boolean
    /** Only present on the GET response — the days this slot may be set to. */
    allowed_days?: number[]
    warning?: string
}

/**
 * The daytime window (inclusive) that any slot's send time must fall within.
 */
export interface AskRidesScheduleTimeWindow {
    min_hour: number
    min_minute: number
    max_hour: number
    max_minute: number
}

/**
 * Response envelope for `GET /api/ask-rides/schedule`.
 */
export interface AskRidesScheduleResponse {
    schedules: Record<AskRidesScheduleSlot, AskRidesScheduleEntry>
    time_window: AskRidesScheduleTimeWindow
}

/**
 * A pickup location row from the management API (`GET /api/pickup-locations`).
 */
export interface ManagedPickupLocation {
    id: number
    name: string
    latitude: number
    longitude: number
    minutes_from_start: number | null
    minutes_to_end: number | null
    is_active: boolean
    is_seeded: boolean
}

/**
 * An undirected travel-time edge between two pickup locations.
 */
export interface PickupLocationEdge {
    id: number
    location_a_id: number
    location_b_id: number
    minutes: number
}

/**
 * Mapping from a campus living location to the pickup location used for it.
 */
export interface LivingLocationMapping {
    living_location: string
    pickup_location_id: number
}

/**
 * Response envelope for `GET /api/pickup-locations`.
 */
export interface ManagedPickupLocationsResponse {
    locations: ManagedPickupLocation[]
    edges: PickupLocationEdge[]
    living_mappings: LivingLocationMapping[]
    pickup_adjustment: number
    unreachable: string[]
}
