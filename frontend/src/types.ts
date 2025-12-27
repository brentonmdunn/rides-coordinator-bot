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
