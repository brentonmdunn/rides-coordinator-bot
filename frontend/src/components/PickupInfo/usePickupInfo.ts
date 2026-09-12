/**
 * usePickupInfo.ts
 *
 * Data layer for the Pickup Info page — one query for the full people
 * list, one for the year/location select options, plus mutations for every
 * management operation. Mutations invalidate the shared query keys (and
 * `['usernames']`, which the rest of the app reads from) so everything stays
 * in sync.
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { apiFetch, ApiError } from '../../lib/api'
import type { PickupInfoOptions, PickupInfoPerson, PickupInfoPersonInput } from '../../types'

export const PICKUP_INFO_QUERY_KEY = ['pickup-info']
export const PICKUP_INFO_OPTIONS_QUERY_KEY = ['pickup-info', 'options']

const JSON_HEADERS = { 'Content-Type': 'application/json' }

/** `POST /api/pickup-info/bulk-delete` accepts at most 500 ids per request. */
const BULK_DELETE_CHUNK = 500

function showMutationError(error: unknown) {
    toast.error(error instanceof ApiError ? error.detail : 'Request failed')
}

/** Extract an inline-displayable message from a mutation error, or null. */
export function formDialogError(error: unknown): string | null {
    if (error instanceof ApiError && (error.status === 400 || error.status === 409)) {
        return error.detail
    }
    return null
}

export function usePickupInfo() {
    const queryClient = useQueryClient()

    const query = useQuery<{ people: PickupInfoPerson[] }>({
        queryKey: PICKUP_INFO_QUERY_KEY,
        queryFn: async () => {
            const response = await apiFetch('/api/pickup-info')
            return response.json()
        },
    })

    const optionsQuery = useQuery<PickupInfoOptions>({
        queryKey: PICKUP_INFO_OPTIONS_QUERY_KEY,
        queryFn: async () => {
            const response = await apiFetch('/api/pickup-info/options')
            return response.json()
        },
    })

    const invalidate = () => {
        void queryClient.invalidateQueries({ queryKey: PICKUP_INFO_QUERY_KEY })
        void queryClient.invalidateQueries({ queryKey: ['usernames'] })
    }

    const createPerson = useMutation({
        mutationFn: async (input: PickupInfoPersonInput) => {
            const response = await apiFetch('/api/pickup-info', {
                method: 'POST',
                headers: JSON_HEADERS,
                body: JSON.stringify(input),
            })
            return response.json() as Promise<PickupInfoPerson>
        },
        onSuccess: invalidate,
        onError: showMutationError,
    })

    const updatePerson = useMutation({
        mutationFn: async ({
            id,
            changes,
        }: {
            id: number
            changes: Partial<PickupInfoPersonInput>
        }) => {
            const response = await apiFetch(`/api/pickup-info/${id}`, {
                method: 'PATCH',
                headers: JSON_HEADERS,
                body: JSON.stringify(changes),
            })
            return response.json() as Promise<PickupInfoPerson>
        },
        onSuccess: invalidate,
        onError: showMutationError,
    })

    const deletePerson = useMutation({
        mutationFn: async (id: number) => {
            await apiFetch(`/api/pickup-info/${id}`, { method: 'DELETE' })
        },
        onSuccess: invalidate,
        onError: showMutationError,
    })

    const bulkDeletePeople = useMutation({
        mutationFn: async (ids: number[]) => {
            const response = await apiFetch('/api/pickup-info/bulk-delete', {
                method: 'POST',
                headers: JSON_HEADERS,
                body: JSON.stringify({ ids }),
            })
            return response.json() as Promise<{ deleted: number }>
        },
        onSuccess: invalidate,
        onError: showMutationError,
    })

    // Deleting everyone can exceed the per-request id cap, so send it in chunks.
    const deleteAllPeople = useMutation({
        mutationFn: async (ids: number[]) => {
            let deleted = 0
            for (let i = 0; i < ids.length; i += BULK_DELETE_CHUNK) {
                const response = await apiFetch('/api/pickup-info/bulk-delete', {
                    method: 'POST',
                    headers: JSON_HEADERS,
                    body: JSON.stringify({ ids: ids.slice(i, i + BULK_DELETE_CHUNK) }),
                })
                const body = (await response.json()) as { deleted: number }
                deleted += body.deleted
            }
            return { deleted }
        },
        onSuccess: ({ deleted }) => {
            invalidate()
            toast.success(`Deleted ${deleted} ${deleted === 1 ? 'person' : 'people'}`)
        },
        onError: showMutationError,
    })

    return {
        query,
        optionsQuery,
        createPerson,
        updatePerson,
        deletePerson,
        bulkDeletePeople,
        deleteAllPeople,
    }
}

export type PickupInfoManagerHook = ReturnType<typeof usePickupInfo>
