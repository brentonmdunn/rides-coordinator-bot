/**
 * numberedMarker.ts
 *
 * Shared Leaflet icons used by the Route Builder views — keeps selected and
 * unselected markers visually consistent between the widget mini-map and the
 * fullscreen map, and avoids the `<Marker icon={undefined}>` pitfall that
 * leaves `marker._icon` unset and crashes on re-render.
 */

import L from 'leaflet'
import markerIcon2x from 'leaflet/dist/images/marker-icon-2x.png'
import markerIcon from 'leaflet/dist/images/marker-icon.png'
import markerShadow from 'leaflet/dist/images/marker-shadow.png'

/** Numbered circle marker for selected pins. */
export function createNumberedIcon(num: number, isNewlyToggled: boolean = false): L.DivIcon {
    const animationClass = isNewlyToggled ? ' animate-[marker-bounce_0.35s_ease-out]' : ''
    return new L.DivIcon({
        html: `<div class="numbered-marker${animationClass}">${num}</div>`,
        className: '',
        iconSize: [28, 28],
        iconAnchor: [14, 14],
        popupAnchor: [0, -16],
    })
}

/**
 * Default blue Leaflet marker with explicit sizing. Used for unselected pins
 * in both the widget mini-map and the fullscreen map. Passing `undefined` to
 * react-leaflet's `<Marker icon>` lets Leaflet's `_initIcon` throw and never
 * attach `marker._icon`, which then crashes `_removeIcon` on unmount with
 * `Cannot read properties of undefined (reading '_leaflet_events')`.
 */
export const defaultMarkerIcon: L.Icon = new L.Icon({
    iconUrl: markerIcon,
    iconRetinaUrl: markerIcon2x,
    shadowUrl: markerShadow,
    iconSize: [25, 41],
    iconAnchor: [12, 41],
    popupAnchor: [1, -34],
    shadowSize: [41, 41],
})
