import { apiFetch } from './api'

export function getCsrfToken(): string {
    const match = document.cookie.match(/(?:^|;\s*)csrf_token=([^;]+)/)
    return match ? decodeURIComponent(match[1]) : ''
}

export async function logout(): Promise<void> {
    try {
        await apiFetch('/api/auth/logout', { method: 'POST' })
    } catch {
        // Ignore errors — we clear cookies server-side, but still navigate away.
    }
    window.location.href = '/login'
}
