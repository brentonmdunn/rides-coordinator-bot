import { useState, useEffect, useCallback, useRef } from 'react'
import { createPortal } from 'react-dom'
import { useQuery } from '@tanstack/react-query'
import { Expand, ArrowLeft, MousePointerClick, ChevronRight, ChevronLeft } from 'lucide-react'
import { getAutomaticDay, useCopyToClipboard } from '../lib/utils'
import { apiFetch } from '../lib/api'
import { Button } from './ui/button'
import { InfoToggleButton, InfoPanel } from './InfoHelp'
import ErrorMessage from './ErrorMessage'
import EditableOutput from './EditableOutput'
import { useTheme } from './use-theme'
import type { PickupLocationsResponse, MakeRouteResponse } from '../types'

import { MapContainer, TileLayer, Marker, Popup, Polyline, Tooltip, useMapEvents } from 'react-leaflet'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import '@luomus/leaflet-smooth-wheel-zoom'
import markerIcon2x from 'leaflet/dist/images/marker-icon-2x.png'
import markerIcon from 'leaflet/dist/images/marker-icon.png'
import markerShadow from 'leaflet/dist/images/marker-shadow.png'
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

// Numbered circle marker for selected pins in fullscreen mode
function createNumberedIcon(num: number, isNewlyToggled: boolean): L.DivIcon {
    const animationClass = isNewlyToggled ? ' animate-[marker-bounce_0.35s_ease-out]' : ''
    return new L.DivIcon({
        html: `<div class="numbered-marker${animationClass}">${num}</div>`,
        className: '',
        iconSize: [28, 28],
        iconAnchor: [14, 14],
        popupAnchor: [0, -16],
    })
}

// Default blue marker with explicit sizing to prevent tooltip misalignment on initial render
const defaultIcon = new L.Icon({
    iconUrl: markerIcon,
    iconRetinaUrl: markerIcon2x,
    shadowUrl: markerShadow,
    iconSize: [25, 41],
    iconAnchor: [12, 41],
    popupAnchor: [1, -34],
    shadowSize: [41, 41],
})

// Deselect handler for clicking empty map space
function MapClickHandler({ onMapClick }: { onMapClick: () => void }) {
    useMapEvents({
        click: () => onMapClick(),
    })
    return null
}

function RouteBuilder() {
    const { theme } = useTheme()

    // State for location selection dropdown (widget mode)
    const [selectedLocation, setSelectedLocation] = useState<string>('')

    // State for selected locations — store keys (e.g., "SEVENTH") not full names
    const [selectedLocationKeys, setSelectedLocationKeys] = useState<string[]>([])
    const [lastToggledLocation, setLastToggledLocation] = useState<string | null>(null)
    const [isPanelExpanded, setIsPanelExpanded] = useState(true)

    const autoMode = getAutomaticDay()
    const [leaveTime, setLeaveTime] = useState(PRESET_TIME_MAP[autoMode])
    const [timeMode, setTimeMode] = useState<TimeModeKey>(autoMode)

    // State for route output
    const [routeOutput, setRouteOutput] = useState<string>('')
    const [originalRouteOutput, setOriginalRouteOutput] = useState<string>('')
    const [routeLoading, setRouteLoading] = useState(false)
    const [routeError, setRouteError] = useState<string>('')
    const { copiedText, copyToClipboard } = useCopyToClipboard(5000)

    // Map bounds for auto-fit (widget mode)
    const [mapBounds, setMapBounds] = useState<L.LatLngBoundsExpression | undefined>(undefined)

    // UI State
    const [showInfo, setShowInfo] = useState(false)

    // Fullscreen transition: two-phase mount/animate pattern
    const [isFullscreenMounted, setIsFullscreenMounted] = useState(false)
    const [isFullscreenVisible, setIsFullscreenVisible] = useState(false)
    const fullscreenTransitionRef = useRef<number | null>(null)

    const openFullscreen = useCallback(() => {
        setIsFullscreenMounted(true)
        // Wait one frame so the browser paints the initial (hidden) state,
        // then apply the visible class to trigger the CSS transition.
        fullscreenTransitionRef.current = requestAnimationFrame(() => {
            fullscreenTransitionRef.current = requestAnimationFrame(() => {
                setIsFullscreenVisible(true)
            })
        })
    }, [])

    const closeFullscreen = useCallback(() => {
        setIsFullscreenVisible(false)
        // Keep mounted until the transition finishes, then unmount.
    }, [])

    // Clean up rAF on unmount
    useEffect(() => {
        return () => {
            if (fullscreenTransitionRef.current !== null) {
                cancelAnimationFrame(fullscreenTransitionRef.current)
            }
        }
    }, [])

    // Fetch available pickup locations via react-query
    const { data: locationsData, isLoading: locationsLoading } = useQuery<PickupLocationsResponse>({
        queryKey: ['pickup-locations'],
        queryFn: async () => {
            const res = await apiFetch('/api/pickup-locations')
            return res.json()
        },
    })

    // Helper function to get location value from key
    const getLocationValue = useCallback(
        (key: string): string => {
            return locationsData?.locations.find((loc) => loc.key === key)?.value || key
        },
        [locationsData]
    )

    // Fetch route geometry via the shared hook
    const routeGeometry = useRouteGeometry(selectedLocationKeys, locationsData, getLocationValue)

    // Update map bounds whenever selected locations change (widget mode)
    useEffect(() => {
        if (!locationsData) return

        if (selectedLocationKeys.length === 0) {
            setMapBounds(undefined)
            return
        }

        if (selectedLocationKeys.length === 1) {
            const name = getLocationValue(selectedLocationKeys[0])
            const singleCoord = locationsData.coordinates[name]
            if (singleCoord) {
                setMapBounds([
                    [singleCoord.lat - 0.01, singleCoord.lng - 0.01],
                    [singleCoord.lat + 0.01, singleCoord.lng + 0.01],
                ])
            }
            return
        }

        const coords = selectedLocationKeys
            .map((key) => locationsData.coordinates[getLocationValue(key)])
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
    }, [selectedLocationKeys, locationsData, getLocationValue])

    // Close fullscreen on Escape key
    useEffect(() => {
        if (!isFullscreenMounted) return

        const onKeyDown = (e: KeyboardEvent) => {
            if (e.key === 'Escape') closeFullscreen()
        }

        window.addEventListener('keydown', onKeyDown)
        return () => window.removeEventListener('keydown', onKeyDown)
    }, [isFullscreenMounted, closeFullscreen])

    // Prevent body scroll when fullscreen overlay is open
    useEffect(() => {
        if (isFullscreenMounted) {
            document.body.style.overflow = 'hidden'
        } else {
            document.body.style.overflow = ''
        }
        return () => {
            document.body.style.overflow = ''
        }
    }, [isFullscreenMounted])

    // Add location to selected list from dropdown (widget mode)
    const addLocation = () => {
        if (selectedLocation && !selectedLocationKeys.includes(selectedLocation)) {
            setSelectedLocationKeys([...selectedLocationKeys, selectedLocation])
            setSelectedLocation('')
        }
    }

    // Toggle a location in or out of the route (fullscreen mode)
    const toggleLocation = (key: string) => {
        setLastToggledLocation(key)
        setSelectedLocationKeys((prev) => {
            if (prev.includes(key)) {
                return prev.filter((k) => k !== key)
            }
            return [...prev, key]
        })
    }

    // Generate route
    const generateRoute = async (e?: React.FormEvent) => {
        e?.preventDefault()
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

    // Revert route to original
    const revertRoute = () => {
        setRouteOutput(originalRouteOutput)
    }

    // --- Fullscreen overlay (rendered via portal) ---
    const fullscreenOverlay = isFullscreenMounted
        ? createPortal(
              <div
                  className={`fixed inset-0 z-50 bg-white dark:bg-zinc-950 transition-all duration-300 ease-out ${
                      isFullscreenVisible
                          ? 'opacity-100 scale-100'
                          : 'opacity-0 scale-[0.97]'
                  }`}
                  onTransitionEnd={(e) => {
                      // After the exit transition finishes, unmount the portal
                      if (e.propertyName === 'opacity' && !isFullscreenVisible) {
                          setIsFullscreenMounted(false)
                      }
                  }}
              >
                  {/* Full-screen interactive map */}
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
                                  icon={isSelected ? createNumberedIcon(orderIndex + 1, lastToggledLocation === loc.key) : defaultIcon}
                                  eventHandlers={{
                                      click: (e) => {
                                          L.DomEvent.stopPropagation(e.originalEvent)
                                          toggleLocation(loc.key)
                                      },
                                  }}
                              >
                                  <Tooltip permanent direction="top" offset={[0, isSelected ? -10 : -36]}>
                                      <span className="font-medium">
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

                  {/* Collapse button (top-left near zoom controls) */}
                  <button
                      onClick={closeFullscreen}
                      className="absolute top-24 left-4 z-[1000] flex items-center gap-2 px-3 py-2 bg-white/95 dark:bg-zinc-900/95 backdrop-blur-sm border border-slate-200 dark:border-zinc-700 rounded-lg shadow-[0_4px_12px_rgba(0,0,0,0.1)] hover:bg-slate-50 dark:hover:bg-zinc-800 transition-colors text-slate-700 dark:text-slate-300"
                      title="Exit fullscreen (Esc)"
                  >
                      <ArrowLeft className="h-4 w-4" />
                      <span className="text-sm font-semibold">Back</span>
                      <span className="text-[10px] font-bold tracking-wider text-slate-400 dark:text-zinc-500 bg-slate-100 dark:bg-zinc-800 px-1.5 py-0.5 rounded ml-1">ESC</span>
                  </button>

                  {/* Right side panel container */}
                  <div className={`absolute top-4 right-4 z-[1000] flex transition-all duration-300 ease-in-out ${
                      isPanelExpanded ? 'w-80' : 'w-10'
                  }`}>
                      
                      {/* Toggle button that hangs off the left edge of the panel */}
                      <button
                          onClick={() => setIsPanelExpanded(!isPanelExpanded)}
                          className={`absolute -left-3.5 top-1/2 -translate-y-1/2 w-7 h-10 flex items-center justify-center bg-white dark:bg-zinc-800 border border-slate-200 dark:border-zinc-700 rounded-lg shadow-md hover:bg-slate-50 dark:hover:bg-zinc-700 transition-colors z-[1001]
                               ${isPanelExpanded ? '' : 'shadow-lg bg-emerald-50 dark:bg-emerald-900/20 border-emerald-200 dark:border-emerald-800'}`}
                          title={isPanelExpanded ? 'Collapse panel' : 'Expand panel'}
                      >
                          {isPanelExpanded ? (
                              <ChevronRight className="h-4 w-4 text-slate-500 dark:text-slate-400" />
                          ) : (
                              <ChevronLeft className="h-4 w-4 text-emerald-600 dark:text-emerald-400" />
                          )}
                      </button>

                      <div className={`w-full max-h-[calc(100vh-2rem)] overflow-hidden rounded-xl border border-slate-200 dark:border-zinc-700 bg-white/95 dark:bg-zinc-900/95 backdrop-blur-md shadow-xl transition-opacity duration-300 ${
                          isPanelExpanded ? 'opacity-100 pointer-events-auto' : 'opacity-0 pointer-events-none'
                      }`}>
                          <div className="p-4 overflow-y-auto max-h-[calc(100vh-2rem)]">
                          {selectedLocationKeys.length === 0 ? (
                              /* Empty state guidance */
                              <div className="flex flex-col items-center text-center py-4">
                                  <div className="w-12 h-12 rounded-full bg-emerald-50 dark:bg-emerald-900/30 flex items-center justify-center mb-3">
                                      <MousePointerClick className="h-6 w-6 text-emerald-600 dark:text-emerald-400" />
                                  </div>
                                  <div className="text-sm font-semibold text-slate-900 dark:text-white mb-1">
                                      Click pins to build your route
                                  </div>
                                  <p className="text-xs text-slate-500 dark:text-slate-400 leading-relaxed">
                                      Click on map markers to add stops. Selected pins turn{' '}
                                      <span className="text-emerald-600 dark:text-emerald-400 font-medium">green</span>{' '}
                                      and are numbered in order.
                                  </p>
                              </div>
                          ) : (
                              /* Route controls */
                              <>
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
                                      onClick={() => generateRoute()}
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
                              </>
                          )}
                          </div>
                      </div>
                  </div>
              </div>,
              document.body
          )
        : null

    // --- Widget card view ---
    return (
        <>
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
                        <button
                            onClick={openFullscreen}
                            className="hidden sm:inline-flex items-center justify-center rounded-md p-1.5 text-slate-500 hover:text-slate-700 hover:bg-slate-100 dark:text-slate-400 dark:hover:text-slate-200 dark:hover:bg-zinc-800 transition-colors"
                            title="Open fullscreen map view"
                        >
                            <Expand className="h-4 w-4" />
                        </button>
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
                                            {locationsData?.locations
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
                                onCopy={() => copyToClipboard(routeOutput)}
                                onRevert={revertRoute}
                                copied={copiedText === routeOutput}
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
                            <RecenterMap bounds={mapBounds} />

                            {selectedLocationKeys.map((key, i) => {
                                const value = getLocationValue(key)
                                const coords = locationsData?.coordinates[value]
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

            {fullscreenOverlay}
        </>
    )
}

export default RouteBuilder
