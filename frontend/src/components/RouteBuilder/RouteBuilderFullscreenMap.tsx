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
import { UCSD_CENTER } from '../MapConstants'
import { createNumberedIcon, defaultMarkerIcon } from './numberedMarker'
import type { PickupLocationsResponse } from '../../types'
import {
    MAP_INITIAL_ZOOM,
    MAP_SMOOTH_WHEEL_ZOOM,
    TOOLTIP_OFFSET_SELECTED,
    TOOLTIP_OFFSET_UNSELECTED,
    ROUTE_POLYLINE_WEIGHT,
    ROUTE_POLYLINE_OPACITY,
} from '../../lib/constants'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

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
            zoom={MAP_INITIAL_ZOOM}
            scrollWheelZoom={false}
            // @ts-expect-error - smoothWheelZoom is an extended option from the plugin
            smoothWheelZoom={true}
            smoothSensitivity={MAP_SMOOTH_WHEEL_ZOOM}
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
                                : defaultMarkerIcon
                        }
                        eventHandlers={{
                            click: (e) => {
                                L.DomEvent.stopPropagation(e.originalEvent)
                                onToggleLocation(loc.key)
                            },
                        }}
                    >
                        {showLocationLabels && (
                            <Tooltip permanent direction="top" offset={[0, isSelected ? TOOLTIP_OFFSET_SELECTED : TOOLTIP_OFFSET_UNSELECTED]}>
                                <span className="font-medium">{loc.value}</span>
                            </Tooltip>
                        )}
                    </Marker>
                )
            })}

            {routeGeometry && (
                <Polyline positions={routeGeometry} color="#10b981" weight={ROUTE_POLYLINE_WEIGHT} opacity={ROUTE_POLYLINE_OPACITY} />
            )}
        </MapContainer>
    )
}
