import { useState, useEffect, useCallback } from 'react'
import { getAutomaticDay } from '../lib/utils'
import { apiFetch } from '../lib/api'
import { Button } from './ui/button'
import { InfoToggleButton, InfoPanel } from './InfoHelp'
import ErrorMessage from './ErrorMessage'
import EditableOutput from './EditableOutput'
import type { PickupLocationsResponse, MakeRouteResponse } from '../types'

import { MapContainer, TileLayer, Marker, Popup, Polyline } from 'react-leaflet'
import L from 'leaflet'
import { RecenterMap, MapInteractionGuard } from './MapShared'
import { UCSD_CENTER, setupLeafletIcons } from './MapConstants'

import { Card, CardHeader, CardTitle, CardContent } from './ui/card'
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from './ui/select'

import {
    PRESET_TIME_MAP,
    type TimeModeKey,
    SortableLocationList,
    ArrivalTimeSelector,
    useRouteGeometry,
} from './routeBuilderShared'

setupLeafletIcons()

function RouteBuilder() {
    // State for available locations from API
    const [availableLocations, setAvailableLocations] = useState<PickupLocationsResponse | null>(null)
    const [locationsLoading, setLocationsLoading] = useState(true)

    // State for location selection dropdown
    const [selectedLocation, setSelectedLocation] = useState<string>('')

    // State for selected locations — store keys (e.g., "SEVENTH") not full names
    const [selectedLocationKeys, setSelectedLocationKeys] = useState<string[]>([])

    const autoMode = getAutomaticDay()
    const [leaveTime, setLeaveTime] = useState(PRESET_TIME_MAP[autoMode])
    const [timeMode, setTimeMode] = useState<TimeModeKey>(autoMode)

    // State for route output
    const [routeOutput, setRouteOutput] = useState<string>('')
    const [originalRouteOutput, setOriginalRouteOutput] = useState<string>('')
    const [routeLoading, setRouteLoading] = useState(false)
    const [routeError, setRouteError] = useState<string>('')
    const [copiedRoute, setCopiedRoute] = useState(false)

    // Map bounds for auto-fit
    const [mapBounds, setMapBounds] = useState<L.LatLngBoundsExpression | undefined>(undefined)

    // UI State
    const [showInfo, setShowInfo] = useState(false)

    // Fetch available pickup locations on mount
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

    // Helper function to get location value from key
    const getLocationValue = useCallback(
        (key: string): string => {
            return availableLocations?.locations.find((loc) => loc.key === key)?.value || key
        },
        [availableLocations]
    )

    // Fetch route geometry via the shared hook
    const routeGeometry = useRouteGeometry(selectedLocationKeys, availableLocations, getLocationValue)

    // Update map bounds whenever selected locations change
    useEffect(() => {
        if (!availableLocations) return

        if (selectedLocationKeys.length === 0) {
            setMapBounds(undefined)
            return
        }

        if (selectedLocationKeys.length === 1) {
            const name = getLocationValue(selectedLocationKeys[0])
            const singleCoord = availableLocations.coordinates[name]
            if (singleCoord) {
                setMapBounds([
                    [singleCoord.lat - 0.01, singleCoord.lng - 0.01],
                    [singleCoord.lat + 0.01, singleCoord.lng + 0.01],
                ])
            }
            return
        }

        const coords = selectedLocationKeys
            .map((key) => availableLocations.coordinates[getLocationValue(key)])
            .filter(Boolean)

        if (coords.length < 2) return

        const lats = coords.map((c) => c.lat)
        const lngs = coords.map((c) => c.lng)
        const latPadding = (Math.max(...lats) - Math.min(...lats)) * 0.1 || 0.01
        const lngPadding = (Math.max(...lngs) - Math.min(...lngs)) * 0.1 || 0.01

        setMapBounds([
            [Math.min(...lats) - latPadding, Math.min(...lngs) - lngPadding],
            [Math.max(...lats) + latPadding, Math.max(...lngs) + lngPadding],
        ])
    }, [selectedLocationKeys, availableLocations, getLocationValue])

    // Add location to selected list from dropdown
    const addLocation = () => {
        if (selectedLocation && !selectedLocationKeys.includes(selectedLocation)) {
            setSelectedLocationKeys([...selectedLocationKeys, selectedLocation])
            setSelectedLocation('')
        }
    }

    // Generate route
    const generateRoute = async (e: React.FormEvent) => {
        e.preventDefault()
        setRouteLoading(true)
        setRouteError('')
        setRouteOutput('')
        setOriginalRouteOutput('')

        try {
            const response = await apiFetch('/api/make-route', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    locations: selectedLocationKeys,
                    leave_time: leaveTime,
                }),
            })

            const result: MakeRouteResponse = await response.json()

            if (result.success && result.route) {
                setRouteOutput(result.route)
                setOriginalRouteOutput(result.route)
            } else {
                setRouteError(result.error || 'Failed to generate route')
            }
        } catch (error) {
            setRouteError(error instanceof Error ? error.message : 'Unknown error')
            console.error('Route generation error:', error)
        } finally {
            setRouteLoading(false)
        }
    }

    // Copy route to clipboard
    const copyRouteToClipboard = async () => {
        try {
            await navigator.clipboard.writeText(routeOutput)
            setCopiedRoute(true)
            setTimeout(() => setCopiedRoute(false), 5000)
        } catch (error) {
            console.error('Failed to copy:', error)
            alert('Failed to copy to clipboard')
        }
    }

    // Revert route to original
    const revertRoute = () => {
        setRouteOutput(originalRouteOutput)
    }

    return (
        <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="flex items-center gap-2">
                    <span>🗺️</span>
                    <span>Route Builder</span>
                </CardTitle>
                <div className="flex items-center gap-2">
                    <InfoToggleButton
                        isOpen={showInfo}
                        onClick={() => setShowInfo(!showInfo)}
                        title="How to use Route Builder"
                    />
                </div>
            </CardHeader>
            <CardContent>
                <InfoPanel
                    isOpen={showInfo}
                    onClose={() => setShowInfo(false)}
                    title="How to use Route Builder"
                >
                    <ol className="list-decimal list-inside space-y-1.5">
                        <li>Select pickup locations from the dropdown in the order you want to visit them.</li>
                        <li>Drag locations to reorder them if needed.</li>
                        <li>Enter the final destination arrival time (e.g., "7:10pm").</li>
                        <li>Click <span className="font-medium">Generate Route</span> to calculate pickup times.</li>
                        <li>Copy the route and paste it into Discord.</li>
                    </ol>
                </InfoPanel>

                <form onSubmit={generateRoute} className="space-y-6">
                    {/* Location Selection Dropdown */}
                    <div>
                        <label className="block">
                            <span className="text-sm font-medium text-slate-700 dark:text-slate-300 mb-2 block">
                                Select Locations
                            </span>
                            <div className="flex gap-2">
                                <Select
                                    value={selectedLocation}
                                    onValueChange={setSelectedLocation}
                                    disabled={locationsLoading}
                                >
                                    <SelectTrigger className="flex-1">
                                        <SelectValue
                                            placeholder={
                                                locationsLoading ? 'Loading locations...' : 'Choose a location...'
                                            }
                                        />
                                    </SelectTrigger>
                                    <SelectContent>
                                        {availableLocations?.locations
                                            .filter((loc) => !selectedLocationKeys.includes(loc.key))
                                            .map((location) => (
                                                <SelectItem key={location.key} value={location.key}>
                                                    {location.value}
                                                </SelectItem>
                                            ))}
                                    </SelectContent>
                                </Select>
                                <Button
                                    type="button"
                                    onClick={addLocation}
                                    disabled={!selectedLocation || locationsLoading}
                                    variant="outline"
                                    className="shrink-0"
                                >
                                    Add Location
                                </Button>
                            </div>
                        </label>
                    </div>

                    {/* Selected Locations with Drag & Drop */}
                    {selectedLocationKeys.length > 0 && (
                        <div className="p-4 bg-slate-50 dark:bg-zinc-800/50 rounded-lg border border-slate-100 dark:border-zinc-700">
                            <div className="text-sm font-medium text-slate-700 dark:text-slate-300 mb-3">
                                Route Order ({selectedLocationKeys.length} location
                                {selectedLocationKeys.length !== 1 ? 's' : ''})
                            </div>
                            <SortableLocationList
                                locationKeys={selectedLocationKeys}
                                getLocationValue={getLocationValue}
                                onRemove={(index) =>
                                    setSelectedLocationKeys((prev) => prev.filter((_, i) => i !== index))
                                }
                                onReorder={setSelectedLocationKeys}
                            />
                        </div>
                    )}

                    {/* Arrival Time Selection */}
                    <div>
                        <span className="text-sm font-medium text-slate-700 dark:text-slate-300 mb-2 block">
                            Arrival Time at Final Destination
                        </span>
                        <ArrivalTimeSelector
                            timeMode={timeMode}
                            leaveTime={leaveTime}
                            onTimeModeChange={(mode, time) => {
                                setTimeMode(mode)
                                setLeaveTime(time)
                            }}
                            onLeaveTimeChange={setLeaveTime}
                            compact={false}
                        />
                    </div>

                    {/* Generate Button */}
                    <div className="pt-2">
                        <Button
                            type="submit"
                            disabled={routeLoading || selectedLocationKeys.length === 0 || !leaveTime}
                            className="w-full sm:w-auto px-8 py-2.5 text-base font-semibold"
                        >
                            {routeLoading ? 'Generating...' : 'Generate Route'}
                        </Button>
                    </div>
                </form>

                {/* Error Display */}
                <div className="mt-6">
                    <ErrorMessage message={routeError} />
                </div>

                {/* Route Output */}
                {routeOutput && (
                    <div className="mt-8 space-y-4 animate-in fade-in slide-in-from-bottom-4 duration-500">
                        <h3 className="text-lg font-semibold text-slate-900 dark:text-white">
                            Generated Route
                        </h3>
                        <EditableOutput
                            value={routeOutput}
                            originalValue={originalRouteOutput}
                            onChange={setRouteOutput}
                            onCopy={copyRouteToClipboard}
                            onRevert={revertRoute}
                            copied={copiedRoute}
                        />
                    </div>
                )}

                {/* Interactive Map view of path */}
                <div className="mt-6 rounded-lg overflow-hidden border border-slate-200 dark:border-zinc-700 relative z-0">
                    <MapContainer
                        center={UCSD_CENTER}
                        zoom={14}
                        scrollWheelZoom={false}
                        dragging={false}
                        style={{ height: '350px', width: '100%' }}
                    >
                        <TileLayer
                            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
                            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                        />
                        <MapInteractionGuard />
                        <RecenterMap bounds={mapBounds} />

                        {selectedLocationKeys.map((key, i) => {
                            const value = getLocationValue(key)
                            const coords = availableLocations?.coordinates[value]
                            if (!coords) return null
                            return (
                                <Marker key={`${key}-${i}`} position={[coords.lat, coords.lng]}>
                                    <Popup>
                                        <strong>{i + 1}.</strong> {value}
                                    </Popup>
                                </Marker>
                            )
                        })}

                        {routeGeometry && (
                            <Polyline positions={routeGeometry} color="#10b981" weight={4} opacity={0.8} />
                        )}
                    </MapContainer>
                </div>
            </CardContent>
        </Card>
    )
}

export default RouteBuilder
