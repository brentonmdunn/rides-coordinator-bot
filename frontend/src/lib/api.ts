/**
 * API Configuration
 *
 * Handles environment-specific API URL configuration and centralized error handling.
 * - Development: Points to localhost:8000
 * - Production: Uses same origin (served by backend)
 */

// Get API base URL based on environment
export const API_BASE_URL = import.meta.env.VITE_API_URL || '';

/**
 * Typed API error with status code and parsed detail from the server.
 */
export class ApiError extends Error {
    status: number
    detail: string

    constructor(status: number, detail: string) {
        super(detail)
        this.name = 'ApiError'
        this.status = status
        this.detail = detail
    }
}

/**
 * Get the full API endpoint URL
 * @param endpoint - API endpoint path (e.g., '/api/hello')
 * @returns Full URL to the API endpoint
 */
export function getApiUrl(endpoint: string): string {
    // Remove leading slash if present to avoid double slashes
    const cleanEndpoint = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;

    if (API_BASE_URL) {
        // If VITE_API_URL is set, use it (dev mode)
        return `${API_BASE_URL}${cleanEndpoint}`;
    }

    // In production, use same origin (backend serves frontend)
    return cleanEndpoint;
}

/**
 * Fetch wrapper with automatic URL resolution and error handling.
 *
 * Checks `res.ok` and throws an {@link ApiError} with the server's
 * `detail` field (FastAPI convention) or a generic status message.
 *
 * @param endpoint - API endpoint path
 * @param options - Fetch options
 * @returns Fetch Response (only on 2xx status)
 * @throws {ApiError} on non-2xx responses
 */
export async function apiFetch(endpoint: string, options?: RequestInit): Promise<Response> {
    const url = getApiUrl(endpoint);
    const response = await fetch(url, options);

    if (!response.ok) {
        let detail: string
        try {
            const body = await response.json()
            detail = body.detail || body.error || body.message || response.statusText
        } catch {
            detail = response.statusText || `Request failed with status ${response.status}`
        }
        throw new ApiError(response.status, detail)
    }

    return response;
}
