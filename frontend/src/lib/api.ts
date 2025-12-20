/**
 * API Configuration
 * 
 * Handles environment-specific API URL configuration.
 * - Development: Points to localhost:8000
 * - Production: Uses same origin (served by backend)
 */

// Get API base URL based on environment
export const API_BASE_URL = import.meta.env.VITE_API_URL || '';

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
 * Fetch wrapper with automatic URL resolution
 * @param endpoint - API endpoint path
 * @param options - Fetch options
 * @returns Fetch promise
 */
export async function apiFetch(endpoint: string, options?: RequestInit): Promise<Response> {
    const url = getApiUrl(endpoint);
    return fetch(url, options);
}
