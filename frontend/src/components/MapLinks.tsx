import { useState, useEffect } from 'react'
import { MapContainer, TileLayer, Marker, Popup } from 'react-leaflet'
import 'leaflet/dist/leaflet.css'
import { apiFetch } from '../lib/api'
import { useCopyToClipboard } from '../lib/utils'
import { useTheme } from './use-theme'
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

import { RecenterMap, MapInteractionGuard } from './MapShared'
import { UCSD_CENTER, setupLeafletIcons } from './MapConstants'

// Fix default marker icon (Leaflet + bundlers lose the default icon paths)
setupLeafletIcons()




function MapLinks() {
    const [availableLocations, setAvailableLocations] =
        useState<PickupLocationsResponse | null>(null)
    const [locationsLoading, setLocationsLoading] = useState(true)
    const [selectedLocation, setSelectedLocation] = useState<string>('')
    const { copiedText, copyToClipboard } = useCopyToClipboard(3000)
    const { theme } = useTheme()

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
                        className="h-48 sm:h-[300px] w-full"
                        style={{ width: '100%' }}
                    >
                        {theme === 'dark' ? (
                            <TileLayer
                                attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>'
                                url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
                            />
                        ) : (
                            <TileLayer
                                attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                                url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                            />
                        )}
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
                                className={`min-w-[6.5rem] transition-colors duration-300 ${isCopied
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
