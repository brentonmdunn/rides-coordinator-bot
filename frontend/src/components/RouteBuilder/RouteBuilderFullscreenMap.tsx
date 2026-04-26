/**
 * RouteBuilderFullscreenMap.tsx
 *
 * The interactive Leaflet map rendered inside the fullscreen overlay.
 * Shared between desktop and mobile fullscreen views.
 *
 * Renders all location markers (numbered when selected), the route polyline,
 * and the tile layer appropriate for the current theme.
 */

import { MapContainer, TileLayer, Marker, Polyline, Tooltip, useMapEvents } from 'react-leaflet'
import L from 'leaflet'
import '@luomus/leaflet-smooth-wheel-zoom'
import markerIcon2x from 'leaflet/dist/images/marker-icon-2x.png'
import markerIcon from 'leaflet/dist/images/marker-icon.png'
import markerShadow from 'leaflet/dist/images/marker-shadow.png'
import { UCSD_CENTER } from '../MapConstants'
import { createNumberedIcon } from './numberedMarker'
import type { PickupLocationsResponse } from '../../types'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Default blue marker with explicit sizing to prevent tooltip misalignment. */
const defaultIcon = new L.Icon({
    iconUrl: markerIcon,
    iconRetinaUrl: markerIcon2x,
    shadowUrl: markerShadow,
    iconSize: [25, 41],
    iconAnchor: [12, 41],
    popupAnchor: [1, -34],
    shadowSize: [41, 41],
})

/** Fires onMapClick when the user clicks empty map space. */
function MapClickHandler({ onMapClick }: { onMapClick: () => void }) {
    useMapEvents({ click: () => onMapClick() })
    return null
}

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

export interface RouteBuilderFullscreenMapProps {
    theme: string
    locationsData: PickupLocationsResponse | undefined
    selectedLocationKeys: string[]
    lastToggledLocation: string | null
    showLocationLabels: boolean
    routeGeometry: [number, number][] | null
    onToggleLocation: (key: string) => void
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function RouteBuilderFullscreenMap({
    theme,
    locationsData,
    selectedLocationKeys,
    lastToggledLocation,
    showLocationLabels,
    routeGeometry,
    onToggleLocation,
}: RouteBuilderFullscreenMapProps) {
    return (
        <MapContainer
            center={UCSD_CENTER}
            zoom={14}
            scrollWheelZoom={false}
            // @ts-expect-error - smoothWheelZoom is an extended option from the plugin
            smoothWheelZoom={true}
            smoothSensitivity={1.5}
            style={{ height: '100%', width: '100%' }}
        >
            {theme === 'dark' ? (
                <TileLayer
                    attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
                    url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
                />
            ) : (
                <TileLayer
                    attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                    url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                />
            )}

            <MapClickHandler onMapClick={() => { }} />

            {locationsData?.locations.map((loc) => {
                const coords = locationsData.coordinates[loc.value]
                if (!coords) return null
                const isSelected = selectedLocationKeys.includes(loc.key)
                const orderIndex = selectedLocationKeys.indexOf(loc.key)

                return (
                    <Marker
                        key={loc.key}
                        position={[coords.lat, coords.lng]}
                        icon={
                            isSelected
                                ? createNumberedIcon(orderIndex + 1, lastToggledLocation === loc.key)
                                : defaultIcon
                        }
                        eventHandlers={{
                            click: (e) => {
                                L.DomEvent.stopPropagation(e.originalEvent)
                                onToggleLocation(loc.key)
                            },
                        }}
                    >
                        {showLocationLabels && (
                            <Tooltip permanent direction="top" offset={[0, isSelected ? -10 : -36]}>
                                <span className="font-medium">{loc.value}</span>
                            </Tooltip>
                        )}
                    </Marker>
                )
            })}

            {routeGeometry && (
                <Polyline positions={routeGeometry} color="#10b981" weight={4} opacity={0.8} />
            )}
        </MapContainer>
    )
}
