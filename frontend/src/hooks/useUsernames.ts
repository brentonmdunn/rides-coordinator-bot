import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '../lib/api'

export function useUsernames() {
    return useQuery<string[]>({
        queryKey: ['usernames'],
        queryFn: async () => {
            const res = await apiFetch('/api/usernames')
            const data = await res.json()
            return data.usernames as string[]
        },
        staleTime: 5 * 60 * 1000,
    })
}
