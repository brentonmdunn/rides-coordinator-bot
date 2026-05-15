import { Outlet, Navigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { apiFetch, ApiError } from '../lib/api'

function AuthGuard() {
    const { error, isLoading } = useQuery({
        queryKey: ['me'],
        queryFn: async () => {
            const res = await apiFetch('/api/me')
            return res.json()
        },
        retry: false,
    })

    if (isLoading) {
        return (
            <div className="min-h-screen flex items-center justify-center text-muted-foreground">
                Loading…
            </div>
        )
    }

    if (error instanceof ApiError && error.status === 401) {
        return <Navigate to="/login" replace />
    }

    if (error) {
        return (
            <div className="min-h-screen flex items-center justify-center text-muted-foreground">
                Something went wrong. <button className="ml-2 underline" onClick={() => window.location.reload()}>Reload</button>
            </div>
        )
    }

    return <Outlet />
}

export default AuthGuard
