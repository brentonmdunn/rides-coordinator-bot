import { useState, useCallback } from 'react'
import { useQuery } from '@tanstack/react-query'
import { MapContainer, TileLayer, Marker, Tooltip, Polyline, useMapEvents } from 'react-leaflet'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import '@luomus/leaflet-smooth-wheel-zoom'
import { UCSD_CENTER, setupLeafletIcons } from '../components/MapConstants'
import { apiFetch } from '../lib/api'
import type { PickupLocationsResponse, MakeRouteResponse } from '../types'
import { Button } from '../components/ui/button'
import EditableOutput from '../components/EditableOutput'
import { getAutomaticDay, useCopyToClipboard } from '../lib/utils'
import {
    PRESET_TIME_MAP,
    type TimeModeKey,
    SortableLocationList,
    ArrivalTimeSelector,
    useRouteGeometry,
} from '../components/routeBuilderShared'

// Fix default marker icon
setupLeafletIcons()

// Green marker for selected pins
const selectedIcon = new L.Icon({
    iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-green.png',
    iconRetinaUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-green.png',
    shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
    iconSize: [25, 41],
    iconAnchor: [12, 41],
    popupAnchor: [1, -34],
    shadowSize: [41, 41],
})

// --- Component to deselect pins by clicking empty map space ---
function MapClickHandler({ onMapClick }: { onMapClick: () => void }) {
    useMapEvents({
        click: () => onMapClick(),
    })
    return null
}

// --- Main page component ---
export default function RouteBuilder() {
    const [selectedLocationKeys, setSelectedLocationKeys] = useState<string[]>([])

    const autoMode = getAutomaticDay()
    const [leaveTime, setLeaveTime] = useState(PRESET_TIME_MAP[autoMode])
    const [timeMode, setTimeMode] = useState<TimeModeKey>(autoMode)

    const [routeOutput, setRouteOutput] = useState('')
    const [originalRouteOutput, setOriginalRouteOutput] = useState('')
    const [routeLoading, setRouteLoading] = useState(false)
    const [routeError, setRouteError] = useState('')
    const { copiedText, copyToClipboard } = useCopyToClipboard(5000)

    const { data: locationsData } = useQuery<PickupLocationsResponse>({
        queryKey: ['pickup-locations'],
        queryFn: async () => {
            const res = await apiFetch('/api/pickup-locations')
            return res.json()
        },
    })

    const getLocationValue = useCallback(
        (key: string): string => {
            return locationsData?.locations.find((loc) => loc.key === key)?.value || key
        },
        [locationsData]
    )

    // Toggle a location in or out of the route
    const toggleLocation = (key: string) => {
        setSelectedLocationKeys((prev) => {
            if (prev.includes(key)) {
                return prev.filter((k) => k !== key)
            }
            return [...prev, key]
        })
    }

    // Fetch route geometry via the shared hook
    const routeGeometry = useRouteGeometry(selectedLocationKeys, locationsData, getLocationValue)

    // Generate route via API
    const generateRoute = async () => {
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
        } finally {
            setRouteLoading(false)
        }
    }

    const revertRoute = () => {
        setRouteOutput(originalRouteOutput)
    }

    return (
        <div className="h-screen w-full relative">
            {/* Full-screen map */}
            <MapContainer
                center={UCSD_CENTER}
                zoom={14}
                scrollWheelZoom={false}
                // @ts-expect-error - smoothWheelZoom is an extended option from the plugin
                smoothWheelZoom={true}
                smoothSensitivity={1.5}
                style={{ height: '100%', width: '100%' }}
            >
                <TileLayer
                    attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                    url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                />
                <MapClickHandler onMapClick={() => {}} />

                {locationsData?.locations.map((loc) => {
                    const coords = locationsData.coordinates[loc.value]
                    if (!coords) return null
                    const isSelected = selectedLocationKeys.includes(loc.key)
                    const orderIndex = selectedLocationKeys.indexOf(loc.key)

                    return (
                        <Marker
                            key={loc.key}
                            position={[coords.lat, coords.lng]}
                            icon={isSelected ? selectedIcon : new L.Icon.Default()}
                            eventHandlers={{
                                click: (e) => {
                                    L.DomEvent.stopPropagation(e.originalEvent)
                                    toggleLocation(loc.key)
                                },
                            }}
                        >
                            <Tooltip permanent direction="top" offset={[0, -36]}>
                                <span className="font-medium">
                                    {isSelected ? `${orderIndex + 1}. ` : ''}
                                    {loc.value}
                                </span>
                            </Tooltip>
                        </Marker>
                    )
                })}

                {routeGeometry && (
                    <Polyline positions={routeGeometry} color="#10b981" weight={4} opacity={0.8} />
                )}
            </MapContainer>

            {/* Right-side route order panel */}
            {selectedLocationKeys.length > 0 && (
                <div className="absolute top-4 right-4 z-[1000] w-72 max-h-[calc(100vh-2rem)] overflow-y-auto rounded-lg border border-slate-200 dark:border-zinc-700 bg-white/95 dark:bg-zinc-900/95 backdrop-blur-sm shadow-xl">
                    <div className="p-4">
                        <div className="flex items-center justify-between mb-3">
                            <div className="text-sm font-semibold text-slate-700 dark:text-slate-300">
                                Route Order ({selectedLocationKeys.length} location
                                {selectedLocationKeys.length !== 1 ? 's' : ''})
                            </div>
                            <Button
                                type="button"
                                variant="ghost"
                                size="sm"
                                onClick={() => setSelectedLocationKeys([])}
                                className="h-6 px-2 text-xs text-slate-500 hover:text-red-600 dark:text-slate-400 dark:hover:text-red-400"
                            >
                                Clear All
                            </Button>
                        </div>

                        <SortableLocationList
                            locationKeys={selectedLocationKeys}
                            getLocationValue={getLocationValue}
                            onRemove={(index) =>
                                setSelectedLocationKeys((prev) => prev.filter((_, i) => i !== index))
                            }
                            onReorder={setSelectedLocationKeys}
                        />

                        {/* Arrival Time Selection */}
                        <div className="mt-4 pt-4 border-t border-slate-200 dark:border-zinc-700">
                            <div className="text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                                Arrival Time
                            </div>
                            <ArrivalTimeSelector
                                timeMode={timeMode}
                                leaveTime={leaveTime}
                                onTimeModeChange={(mode, time) => {
                                    setTimeMode(mode)
                                    setLeaveTime(time)
                                }}
                                onLeaveTimeChange={setLeaveTime}
                                compact={true}
                            />
                        </div>

                        {/* Generate Button */}
                        <Button
                            onClick={generateRoute}
                            disabled={routeLoading || selectedLocationKeys.length === 0 || !leaveTime}
                            className="w-full mt-3"
                        >
                            {routeLoading ? 'Generating...' : 'Generate Route'}
                        </Button>

                        {/* Error */}
                        {routeError && (
                            <div className="mt-2 text-xs text-red-600 dark:text-red-400">
                                {routeError}
                            </div>
                        )}

                        {/* Route Output */}
                        {routeOutput && (
                            <div className="mt-3">
                                <div className="text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                                    Generated Route
                                </div>
                                <EditableOutput
                                    value={routeOutput}
                                    originalValue={originalRouteOutput}
                                    onChange={setRouteOutput}
                                    onCopy={() => copyToClipboard(routeOutput)}
                                    onRevert={revertRoute}
                                    copied={copiedText === routeOutput}
                                    minHeight="min-h-[120px]"
                                />
                            </div>
                        )}
                    </div>
                </div>
            )}
        </div>
    )
}
