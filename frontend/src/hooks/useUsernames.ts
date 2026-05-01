import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '../lib/api'

export interface UsernameEntry {
    username: string
    name: string
}

export function useUsernames() {
    return useQuery<UsernameEntry[]>({
        queryKey: ['usernames'],
        queryFn: async () => {
            const res = await apiFetch('/api/usernames')
            const data = await res.json()
            return data.users as UsernameEntry[]
        },
        staleTime: 5 * 60 * 1000,
    })
}
