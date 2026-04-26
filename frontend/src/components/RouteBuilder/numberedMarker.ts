/**
 * numberedMarker.ts
 *
 * Shared factory for the numbered-circle Leaflet markers used in both the
 * widget mini-map and the fullscreen map so the visual state of selected
 * stops (order, bounce-on-add) stays consistent across views.
 */

import L from 'leaflet'

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
