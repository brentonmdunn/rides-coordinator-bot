import { useEffect, useState } from 'react'
import type { PickupLocationsResponse } from '../../types'

export interface RouteGeometryResult {
    /** Array of [lat, lng] pairs for the Leaflet Polyline, or null when unavailable. */
    geometry: [number, number][] | null
    /** Total OSRM driving duration in seconds, or null. */
    totalDuration: number | null
    /** Total OSRM driving distance in meters, or null. */
    totalDistance: number | null
    /** Per-leg durations in seconds (length === selectedLocationKeys.length - 1). */
    legDurations: number[]
}

const EMPTY_RESULT: RouteGeometryResult = {
    geometry: null,
    totalDuration: null,
    totalDistance: null,
    legDurations: [],
}

/**
 * Fetches a driving route from OSRM whenever `selectedLocationKeys` or
 * `locationsData` changes. Returns the polyline geometry plus aggregate and
 * per-leg metadata so callers can render ETA chips and per-leg drive times.
 */
export function useRouteGeometry(
    selectedLocationKeys: string[],
    locationsData: PickupLocationsResponse | null | undefined,
    getLocationValue: (key: string) => string
): RouteGeometryResult {
    const [result, setResult] = useState<RouteGeometryResult>(EMPTY_RESULT)

    useEffect(() => {
        if (!locationsData || selectedLocationKeys.length < 2) {
            // Defer to avoid synchronous state updates during render
            Promise.resolve().then(() => setResult(EMPTY_RESULT))
            return
        }

        const coords = selectedLocationKeys
            .map((key) => {
                const name = getLocationValue(key)
                return locationsData.coordinates[name]
            })
            .filter(Boolean)

        if (coords.length < 2) {
            Promise.resolve().then(() => setResult(EMPTY_RESULT))
            return
        }

        const coordsString = coords.map((c) => `${c.lng},${c.lat}`).join(';')

        let isMounted = true

        const fetchRoute = async () => {
            try {
                const res = await fetch(
                    `https://router.project-osrm.org/route/v1/driving/${coordsString}?overview=full&geometries=geojson`
                )
                if (!res.ok) return
                const data = await res.json()
                if (data.routes && data.routes.length > 0) {
                    const route = data.routes[0]
                    const latLngs: [number, number][] = route.geometry.coordinates.map(
                        (c: [number, number]) => [c[1], c[0]] as [number, number]
                    )
                    const legDurations: number[] = Array.isArray(route.legs)
                        ? route.legs.map((leg: { duration: number }) => leg.duration)
                        : []
                    if (isMounted) {
                        setResult({
                            geometry: latLngs,
                            totalDuration: typeof route.duration === 'number' ? route.duration : null,
                            totalDistance: typeof route.distance === 'number' ? route.distance : null,
                            legDurations,
                        })
                    }
                }
            } catch (err) {
                console.error('Failed to fetch route geometry', err)
            }
        }

        fetchRoute()

        return () => {
            isMounted = false
        }
    }, [selectedLocationKeys, locationsData, getLocationValue])

    return result
}
