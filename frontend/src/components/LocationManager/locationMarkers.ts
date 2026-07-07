/**
 * locationMarkers.ts
 *
 * DivIcon dot markers for the Locations management map. CSS-based (semantic
 * color tokens) so they stay theme-aware, unlike the stock Leaflet image
 * pins. Icons are created per variant and memoized — passing `undefined` to
 * react-leaflet's `<Marker icon>` crashes on unmount (see numberedMarker.ts).
 */

import L from 'leaflet'

export type LocationMarkerVariant =
    | 'active'
    | 'inactive'
    | 'unreachable'
    | 'edge-start'

const VARIANT_CLASSES: Record<LocationMarkerVariant, string> = {
    active: 'bg-info',
    inactive: 'bg-muted-foreground opacity-60',
    unreachable: 'bg-destructive',
    'edge-start': 'bg-info ring-4 ring-accent/50',
}

const iconCache = new Map<LocationMarkerVariant, L.DivIcon>()

export function createLocationIcon(variant: LocationMarkerVariant): L.DivIcon {
    const cached = iconCache.get(variant)
    if (cached) return cached

    const icon = new L.DivIcon({
        html: `<div class="h-4 w-4 rounded-full border-2 border-background shadow-md ${VARIANT_CLASSES[variant]}"></div>`,
        className: '',
        iconSize: [16, 16],
        iconAnchor: [8, 8],
        popupAnchor: [0, -10],
        tooltipAnchor: [0, -10],
    })
    iconCache.set(variant, icon)
    return icon
}
