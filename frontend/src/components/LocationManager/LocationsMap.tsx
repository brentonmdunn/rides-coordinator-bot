/**
 * LocationsMap.tsx
 *
 * Interactive map for the Locations management page. Shows a dot marker per
 * location and a polyline per travel-time edge (minutes rendered as a
 * permanent tooltip at the line's midpoint). Supports three modes:
 *
 * - view: click a marker for a popup with edit/deactivate/delete actions,
 *   click an edge to edit its minutes.
 * - add-location: click anywhere on the map to drop a pin (opens the create
 *   form pre-filled with the clicked coordinates).
 * - add-edge: click two markers in sequence to connect them.
 */

import { MapContainer, TileLayer, Marker, Polyline, Popup, Tooltip, useMapEvents } from 'react-leaflet'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { Button } from '../ui/button'
import { MapInteractionGuard, RecenterMap } from '../MapShared'
import { UCSD_CENTER } from '../MapConstants'
import { ROUTE_POLYLINE_WEIGHT, ROUTE_POLYLINE_OPACITY } from '../../lib/constants'
import { createLocationIcon, type LocationMarkerVariant } from './locationMarkers'
import type { ManagedPickupLocation, PickupLocationEdge } from '../../types'

export type MapMode = 'view' | 'add-location' | 'add-edge'

// Emerald map accent — intentional exception to the semantic-token rule,
// matching the Route Builder polylines.
const EDGE_COLOR = '#10b981'

interface LocationsMapProps {
    theme: string
    locations: ManagedPickupLocation[]
    edges: PickupLocationEdge[]
    unreachable: Set<string>
    showInactive: boolean
    mode: MapMode
    /** First marker clicked while in add-edge mode. */
    pendingEdgeStartId: number | null
    /** Set to pan the map (e.g. from a table row click). */
    flyTarget: [number, number] | undefined
    onMapClick: (latitude: number, longitude: number) => void
    onMarkerClick: (location: ManagedPickupLocation) => void
    onEdgeClick: (edge: PickupLocationEdge) => void
    onEditLocation: (location: ManagedPickupLocation) => void
    onToggleActive: (location: ManagedPickupLocation) => void
    onDeleteLocation: (location: ManagedPickupLocation) => void
}

function MapClickHandler({ onClick }: { onClick: (lat: number, lng: number) => void }) {
    useMapEvents({
        click: (e) => onClick(e.latlng.lat, e.latlng.lng),
    })
    return null
}

function markerVariant(
    location: ManagedPickupLocation,
    unreachable: Set<string>,
    pendingEdgeStartId: number | null
): LocationMarkerVariant {
    if (location.id === pendingEdgeStartId) return 'edge-start'
    if (!location.is_active) return 'inactive'
    if (unreachable.has(location.name)) return 'unreachable'
    return 'active'
}

export function LocationsMap({
    theme,
    locations,
    edges,
    unreachable,
    showInactive,
    mode,
    pendingEdgeStartId,
    flyTarget,
    onMapClick,
    onMarkerClick,
    onEdgeClick,
    onEditLocation,
    onToggleActive,
    onDeleteLocation,
}: LocationsMapProps) {
    const locationsById = new Map(locations.map((loc) => [loc.id, loc]))
    const visibleLocations = locations.filter((loc) => loc.is_active || showInactive)

    return (
        <div className="rounded-lg overflow-hidden border border-border relative z-0">
            <MapContainer
                center={UCSD_CENTER}
                zoom={14}
                scrollWheelZoom={false}
                className="h-72 sm:h-[420px] w-full"
                style={{ width: '100%' }}
            >
                {theme === 'dark' ? (
                    <TileLayer
                        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>'
                        url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
                    />
                ) : (
                    <TileLayer
                        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
                        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                    />
                )}
                <MapInteractionGuard />
                <RecenterMap center={flyTarget} />
                {mode === 'add-location' && <MapClickHandler onClick={onMapClick} />}

                {edges.map((edge) => {
                    const a = locationsById.get(edge.location_a_id)
                    const b = locationsById.get(edge.location_b_id)
                    if (!a || !b) return null
                    if (!showInactive && (!a.is_active || !b.is_active)) return null
                    return (
                        <Polyline
                            key={edge.id}
                            positions={[
                                [a.latitude, a.longitude],
                                [b.latitude, b.longitude],
                            ]}
                            color={EDGE_COLOR}
                            weight={ROUTE_POLYLINE_WEIGHT}
                            opacity={a.is_active && b.is_active ? ROUTE_POLYLINE_OPACITY : 0.3}
                            eventHandlers={{
                                click: (e) => {
                                    L.DomEvent.stopPropagation(e.originalEvent)
                                    if (mode === 'view') onEdgeClick(edge)
                                },
                            }}
                        >
                            <Tooltip permanent direction="center" className="font-medium">
                                {edge.minutes} min
                            </Tooltip>
                        </Polyline>
                    )
                })}

                {visibleLocations.map((location) => (
                    <Marker
                        key={location.id}
                        position={[location.latitude, location.longitude]}
                        icon={createLocationIcon(
                            markerVariant(location, unreachable, pendingEdgeStartId)
                        )}
                        eventHandlers={{
                            click: (e) => {
                                if (mode === 'add-edge') {
                                    L.DomEvent.stopPropagation(e.originalEvent)
                                    onMarkerClick(location)
                                }
                            },
                        }}
                    >
                        <Tooltip direction="top">
                            <span className="font-medium">{location.name}</span>
                        </Tooltip>
                        {mode === 'view' && (
                            <Popup>
                                <div className="space-y-2 min-w-44">
                                    <div>
                                        <p className="font-semibold">{location.name}</p>
                                        <p className="text-xs">
                                            {location.latitude.toFixed(6)}, {location.longitude.toFixed(6)}
                                        </p>
                                        {!location.is_active && (
                                            <p className="text-xs italic">Inactive</p>
                                        )}
                                        {unreachable.has(location.name) && (
                                            <p className="text-xs font-medium">
                                                ⚠ No route to destination
                                            </p>
                                        )}
                                    </div>
                                    <div className="flex flex-wrap gap-1.5">
                                        <Button
                                            size="sm"
                                            variant="outline"
                                            onClick={() => onEditLocation(location)}
                                        >
                                            Edit
                                        </Button>
                                        <Button
                                            size="sm"
                                            variant="outline"
                                            onClick={() => onToggleActive(location)}
                                        >
                                            {location.is_active ? 'Deactivate' : 'Reactivate'}
                                        </Button>
                                        <Button
                                            size="sm"
                                            variant="destructive"
                                            onClick={() => onDeleteLocation(location)}
                                        >
                                            Delete
                                        </Button>
                                    </div>
                                </div>
                            </Popup>
                        )}
                    </Marker>
                ))}
            </MapContainer>
        </div>
    )
}
