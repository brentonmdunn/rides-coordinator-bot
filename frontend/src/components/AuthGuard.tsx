import { useEffect } from 'react'
import { Outlet, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { apiFetch, ApiError } from '../lib/api'

function AuthGuard() {
    const navigate = useNavigate()

    const { error, isLoading } = useQuery({
        queryKey: ['me'],
        queryFn: async () => {
            const res = await apiFetch('/api/me')
            return res.json()
        },
        retry: false,
    })

    useEffect(() => {
        if (error instanceof ApiError && error.status === 401) {
            navigate('/login', { replace: true })
        }
    }, [error, navigate])

    if (isLoading) {
        return (
            <div className="min-h-screen flex items-center justify-center text-slate-500">
                Loading…
            </div>
        )
    }

    if (error) {
        if (error instanceof ApiError && error.status === 401) {
            return null
        }
        return (
            <div className="min-h-screen flex items-center justify-center text-slate-500">
                Something went wrong. <button className="ml-2 underline" onClick={() => window.location.reload()}>Reload</button>
            </div>
        )
    }

    return <Outlet />
}

export default AuthGuard
