import { useEffect, useState } from 'react'
import type { PickupLocationsResponse } from '../../types'

/**
 * Fetches a driving route geometry from OSRM whenever `selectedLocationKeys`
 * or `locationsData` changes. Returns an array of [lat, lng] pairs suitable
 * for a Leaflet Polyline, or null if fewer than 2 locations are selected.
 */
export function useRouteGeometry(
    selectedLocationKeys: string[],
    locationsData: PickupLocationsResponse | null | undefined,
    getLocationValue: (key: string) => string
): [number, number][] | null {
    const [routeGeometry, setRouteGeometry] = useState<[number, number][] | null>(null)

    useEffect(() => {
        if (!locationsData || selectedLocationKeys.length < 2) {
            // Wait internally before resetting state to avoid synchronous state updates during render
            Promise.resolve().then(() => setRouteGeometry(null))
            return
        }

        const coords = selectedLocationKeys
            .map((key) => {
                const name = getLocationValue(key)
                return locationsData.coordinates[name]
            })
            .filter(Boolean)

        if (coords.length < 2) {
            Promise.resolve().then(() => setRouteGeometry(null))
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
                    const latLngs = data.routes[0].geometry.coordinates.map(
                        (c: [number, number]) => [c[1], c[0]] as [number, number]
                    )
                    if (isMounted) {
                        setRouteGeometry(latLngs)
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

    return routeGeometry
}
