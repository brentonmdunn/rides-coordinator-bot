/**
 * useLocationManager.ts
 *
 * Data layer for the Locations management page — one query for the full
 * pickup-location graph plus mutations for every management operation. All
 * mutations invalidate the shared query key so every section stays in sync.
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { apiFetch } from '../../lib/api'
import type { ManagedPickupLocationsResponse } from '../../types'

export const PICKUP_LOCATIONS_QUERY_KEY = ['pickup-locations']

export interface LocationInput {
    name: string
    latitude: number
    longitude: number
    minutes_from_start?: number | null
    minutes_to_end?: number | null
}

export interface LocationPatch extends Partial<LocationInput> {
    is_active?: boolean
}

export interface EdgeInput {
    location_a_id: number
    location_b_id: number
    minutes: number
}

const JSON_HEADERS = { 'Content-Type': 'application/json' }

function showMutationError(error: unknown) {
    toast.error(error instanceof Error ? error.message : 'Request failed')
}

export function useLocationManager() {
    const queryClient = useQueryClient()

    const query = useQuery<ManagedPickupLocationsResponse>({
        queryKey: PICKUP_LOCATIONS_QUERY_KEY,
        queryFn: async () => {
            const response = await apiFetch('/api/pickup-locations')
            return response.json()
        },
    })

    const invalidate = () =>
        queryClient.invalidateQueries({ queryKey: PICKUP_LOCATIONS_QUERY_KEY })

    const createLocation = useMutation({
        mutationFn: async (input: LocationInput) => {
            await apiFetch('/api/pickup-locations', {
                method: 'POST',
                headers: JSON_HEADERS,
                body: JSON.stringify(input),
            })
        },
        onSuccess: invalidate,
        onError: showMutationError,
    })

    const updateLocation = useMutation({
        mutationFn: async ({ id, patch }: { id: number; patch: LocationPatch }) => {
            await apiFetch(`/api/pickup-locations/${id}`, {
                method: 'PATCH',
                headers: JSON_HEADERS,
                body: JSON.stringify(patch),
            })
        },
        onSuccess: invalidate,
        onError: showMutationError,
    })

    const deleteLocation = useMutation({
        mutationFn: async (id: number) => {
            await apiFetch(`/api/pickup-locations/${id}`, { method: 'DELETE' })
        },
        onSuccess: invalidate,
        onError: showMutationError,
    })

    const upsertEdge = useMutation({
        mutationFn: async (input: EdgeInput) => {
            await apiFetch('/api/pickup-locations/edges', {
                method: 'PUT',
                headers: JSON_HEADERS,
                body: JSON.stringify(input),
            })
        },
        onSuccess: invalidate,
        onError: showMutationError,
    })

    const deleteEdge = useMutation({
        mutationFn: async (id: number) => {
            await apiFetch(`/api/pickup-locations/edges/${id}`, { method: 'DELETE' })
        },
        onSuccess: invalidate,
        onError: showMutationError,
    })

    const setLivingMapping = useMutation({
        mutationFn: async ({
            living_location,
            pickup_location_id,
        }: {
            living_location: string
            pickup_location_id: number
        }) => {
            await apiFetch(
                `/api/pickup-locations/living-mappings/${encodeURIComponent(living_location)}`,
                {
                    method: 'PUT',
                    headers: JSON_HEADERS,
                    body: JSON.stringify({ pickup_location_id }),
                }
            )
        },
        onSuccess: invalidate,
        onError: showMutationError,
    })

    const savePickupAdjustment = useMutation({
        mutationFn: async (value: number) => {
            await apiFetch('/api/pickup-locations/settings/pickup-adjustment', {
                method: 'PUT',
                headers: JSON_HEADERS,
                body: JSON.stringify({ value }),
            })
        },
        onSuccess: () => {
            invalidate()
            toast.success('Pickup adjustment saved')
        },
        onError: showMutationError,
    })

    return {
        query,
        createLocation,
        updateLocation,
        deleteLocation,
        upsertEdge,
        deleteEdge,
        setLivingMapping,
        savePickupAdjustment,
    }
}

export type LocationManager = ReturnType<typeof useLocationManager>
