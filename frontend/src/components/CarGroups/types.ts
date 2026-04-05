export interface Rider {
    id: string;
    discordUsername: string;
    pickupLocation: string;
    earliestLeaveTime: string;
    name?: string;
}

export interface CarGroup {
    id: string;
    riders: Rider[];
}
