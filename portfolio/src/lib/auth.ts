export function getCsrfToken(): string {
    const match = document.cookie.match(/(?:^|;\s*)csrf_token=([^;]+)/)
    return match ? decodeURIComponent(match[1]) : ''
}

export async function logout(): Promise<void> {
    // Demo mode: no real logout — just dispatch a demo-action event
    window.dispatchEvent(
        new CustomEvent('demo-action', {
            detail: { message: 'Demo mode: logout is disabled.' },
        })
    )
}
