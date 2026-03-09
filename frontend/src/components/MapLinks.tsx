import { useState, useEffect, useCallback } from 'react'
import { MapContainer, TileLayer, Marker, Popup, useMap } from 'react-leaflet'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { apiFetch } from '../lib/api'
import { useCopyToClipboard } from '../lib/utils'
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from './ui/select'
import { Card, CardHeader, CardTitle, CardContent } from './ui/card'
import { Copy, Check, ExternalLink } from 'lucide-react'
import { Button } from './ui/button'
import type { PickupLocationsResponse } from '../types'

// Fix default marker icon (Leaflet + bundlers lose the default icon paths)
import markerIcon2x from 'leaflet/dist/images/marker-icon-2x.png'
import markerIcon from 'leaflet/dist/images/marker-icon.png'
import markerShadow from 'leaflet/dist/images/marker-shadow.png'

delete (L.Icon.Default.prototype as unknown as Record<string, unknown>)._getIconUrl
L.Icon.Default.mergeOptions({
    iconRetinaUrl: markerIcon2x,
    iconUrl: markerIcon,
    shadowUrl: markerShadow,
})

// UCSD campus center (fallback)
const UCSD_CENTER: [number, number] = [32.8801, -117.2340]

// Component to recenter map when selected location changes
function RecenterMap({ center }: { center: [number, number] }) {
    const map = useMap()
    useEffect(() => {
        map.flyTo(center, 16, { duration: 0.8 })
    }, [center, map])
    return null
}

// Prevents accidental map interaction while scrolling the page.
// Desktop: Cmd/Ctrl + scroll to zoom (dragging is free).
// Mobile: Two-finger drag to pan, pinch-zoom works freely.
//
// To disable the guard:
//   1. Remove <MapInteractionGuard /> from inside the MapContainer
//   2. Change MapContainer props to: scrollWheelZoom={true} dragging={true}
//      and remove the dragging={false} prop
function MapInteractionGuard() {
    const map = useMap()
    const [hintMessage, setHintMessage] = useState<string | null>(null)

    const isTouchDevice =
        typeof window !== 'undefined' && 'ontouchstart' in window

    const showHintTemporarily = useCallback(
        (msg: string) => {
            setHintMessage(msg)
            const id = setTimeout(() => setHintMessage(null), 1500)
            return () => clearTimeout(id)
        },
        [setHintMessage]
    )

    // Desktop: gate scroll-zoom behind Cmd/Ctrl, allow free dragging
    useEffect(() => {
        if (isTouchDevice) return

        map.scrollWheelZoom.disable()
        map.dragging.enable()

        const onKeyDown = (e: KeyboardEvent) => {
            if (e.metaKey || e.ctrlKey) {
                map.scrollWheelZoom.enable()
                setHintMessage(null)
            }
        }
        const onKeyUp = () => {
            map.scrollWheelZoom.disable()
        }

        window.addEventListener('keydown', onKeyDown)
        window.addEventListener('keyup', onKeyUp)
        window.addEventListener('blur', () => map.scrollWheelZoom.disable())

        return () => {
            window.removeEventListener('keydown', onKeyDown)
            window.removeEventListener('keyup', onKeyUp)
        }
    }, [map, isTouchDevice])

    // Desktop: show hint on scroll without modifier
    useEffect(() => {
        if (isTouchDevice) return
        const container = map.getContainer()

        const onWheel = (e: WheelEvent) => {
            if (!e.metaKey && !e.ctrlKey) {
                showHintTemporarily('Use ⌘/Ctrl + scroll to zoom')
            }
        }

        container.addEventListener('wheel', onWheel, { passive: true })
        return () => container.removeEventListener('wheel', onWheel)
    }, [map, isTouchDevice, showHintTemporarily])

    // Mobile: require two-finger drag, allow pinch-zoom
    useEffect(() => {
        if (!isTouchDevice) return

        map.dragging.disable()

        const container = map.getContainer()

        const onTouchStart = (e: TouchEvent) => {
            if (e.touches.length >= 2) {
                map.dragging.enable()
            } else {
                map.dragging.disable()
                showHintTemporarily('Use two fingers to move the map')
            }
        }

        const onTouchEnd = () => {
            map.dragging.disable()
        }

        container.addEventListener('touchstart', onTouchStart, {
            passive: true,
        })
        container.addEventListener('touchend', onTouchEnd, { passive: true })
        return () => {
            container.removeEventListener('touchstart', onTouchStart)
            container.removeEventListener('touchend', onTouchEnd)
        }
    }, [map, isTouchDevice, showHintTemporarily])

    return hintMessage ? (
        <div className="absolute inset-0 z-[1000] flex items-center justify-center pointer-events-none">
            <div className="bg-black/70 text-white text-sm px-4 py-2 rounded-lg shadow-lg">
                {hintMessage}
            </div>
        </div>
    ) : null
}

function MapLinks() {
    const [availableLocations, setAvailableLocations] =
        useState<PickupLocationsResponse | null>(null)
    const [locationsLoading, setLocationsLoading] = useState(true)
    const [selectedLocation, setSelectedLocation] = useState<string>('')
    const { copiedText, copyToClipboard } = useCopyToClipboard(3000)

    useEffect(() => {
        const fetchLocations = async () => {
            try {
                const response = await apiFetch('/api/pickup-locations')
                const data: PickupLocationsResponse = await response.json()
                setAvailableLocations(data)
            } catch (error) {
                console.error('Failed to fetch pickup locations:', error)
            } finally {
                setLocationsLoading(false)
            }
        }

        fetchLocations()
    }, [])

    // Get the display name for the selected location key
    const selectedLocationName =
        availableLocations?.locations.find(
            (loc) => loc.key === selectedLocation
        )?.value ?? ''

    // Get the Google Maps URL for the selected location
    const selectedMapUrl = selectedLocationName
        ? (availableLocations?.map_links[selectedLocationName] ?? null)
        : null

    // Get coordinates for the selected location
    const selectedCoords = selectedLocationName
        ? (availableLocations?.coordinates[selectedLocationName] ?? null)
        : null

    const mapCenter: [number, number] = selectedCoords
        ? [selectedCoords.lat, selectedCoords.lng]
        : UCSD_CENTER

    const isCopied = copiedText === selectedMapUrl

    return (
        <Card>
            <CardHeader className="pb-2">
                <CardTitle className="flex items-center gap-2">
                    <span>📍</span>
                    <span>Pickup Directions</span>
                </CardTitle>
            </CardHeader>
            <CardContent>
                <p className="text-sm text-slate-500 dark:text-slate-400 mb-4">
                    Select a pickup location to view it on the map and copy the
                    Google Maps link.
                </p>

                {/* Location Dropdown */}
                <div>
                    <Select
                        value={selectedLocation}
                        onValueChange={setSelectedLocation}
                        disabled={locationsLoading}
                    >
                        <SelectTrigger id="map-links-location-select" className="w-full">
                            <SelectValue
                                placeholder={
                                    locationsLoading
                                        ? 'Loading locations...'
                                        : 'Choose a location...'
                                }
                            />
                        </SelectTrigger>
                        <SelectContent>
                            {availableLocations?.locations
                                .filter(
                                    (loc) =>
                                        availableLocations.coordinates[
                                        loc.value
                                        ] != null
                                )
                                .map((location) => (
                                    <SelectItem
                                        key={location.key}
                                        value={location.key}
                                    >
                                        {location.value}
                                    </SelectItem>
                                ))}
                        </SelectContent>
                    </Select>
                </div>

                {/* Map */}
                <div className="mt-4 rounded-lg overflow-hidden border border-slate-200 dark:border-zinc-700 relative z-0">
                    <MapContainer
                        center={mapCenter}
                        zoom={selectedCoords ? 16 : 14}
                        scrollWheelZoom={false}
                        dragging={false}
                        style={{ height: '300px', width: '100%' }}
                    >
                        <TileLayer
                            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                        />
                        <MapInteractionGuard />
                        {selectedCoords && (
                            <>
                                <RecenterMap
                                    center={[
                                        selectedCoords.lat,
                                        selectedCoords.lng,
                                    ]}
                                />
                                <Marker
                                    position={[
                                        selectedCoords.lat,
                                        selectedCoords.lng,
                                    ]}
                                >
                                    <Popup>{selectedLocationName}</Popup>
                                </Marker>
                            </>
                        )}
                    </MapContainer>
                </div>

                {/* Action Buttons */}
                {selectedMapUrl && (
                    <div className="mt-4 p-4 bg-slate-50 dark:bg-zinc-800/50 rounded-lg border border-slate-100 dark:border-zinc-700 animate-in fade-in slide-in-from-bottom-2 duration-300">
                        <div className="text-sm font-medium text-slate-700 dark:text-slate-300 mb-3">
                            {selectedLocationName}
                        </div>
                        <div className="flex flex-wrap gap-2">
                            <Button
                                id="map-links-copy-btn"
                                type="button"
                                variant="outline"
                                size="sm"
                                onClick={() => copyToClipboard(selectedMapUrl)}
                                className={`transition-all duration-300 ${isCopied
                                    ? 'border-green-500 text-green-600 dark:text-green-400'
                                    : ''
                                    }`}
                            >
                                {isCopied ? (
                                    <>
                                        <Check className="h-4 w-4 mr-1.5" />
                                        Copied!
                                    </>
                                ) : (
                                    <>
                                        <Copy className="h-4 w-4 mr-1.5" />
                                        Copy Link
                                    </>
                                )}
                            </Button>
                            <Button
                                id="map-links-open-btn"
                                type="button"
                                variant="outline"
                                size="sm"
                                asChild
                            >
                                <a
                                    href={selectedMapUrl}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                >
                                    <ExternalLink className="h-4 w-4 mr-1.5" />
                                    Open in Maps
                                </a>
                            </Button>
                        </div>
                    </div>
                )}
            </CardContent>
        </Card>
    )
}

export default MapLinks
