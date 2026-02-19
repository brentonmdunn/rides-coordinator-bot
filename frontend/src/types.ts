export interface HousingGroup {
    emoji: string
    count: number
    locations: {
        [location: string]: Array<{
            name: string
            discord_username: string | null
        }>
    }
}

export interface LocationData {
    housing_groups: {
        [groupName: string]: HousingGroup
    }
    unknown_users: string[]
}

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
