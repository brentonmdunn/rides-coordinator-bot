import L from 'leaflet'

// Fix default marker icon (Leaflet + bundlers lose the default icon paths)
import markerIcon2x from 'leaflet/dist/images/marker-icon-2x.png'
import markerIcon from 'leaflet/dist/images/marker-icon.png'
import markerShadow from 'leaflet/dist/images/marker-shadow.png'

export function setupLeafletIcons() {
    delete (L.Icon.Default.prototype as unknown as Record<string, unknown>)._getIconUrl
    L.Icon.Default.mergeOptions({
        iconRetinaUrl: markerIcon2x,
        iconUrl: markerIcon,
        shadowUrl: markerShadow,
    })
}

// UCSD campus center (fallback)
export const UCSD_CENTER: [number, number] = [32.8801, -117.2340]
