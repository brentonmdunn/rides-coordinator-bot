/**
 * RouteBuilderWidget.tsx
 *
 * The card / widget view of the Route Builder — the default display when not
 * in fullscreen mode. Contains the multi-select location combobox, sortable
 * stop list, arrival time selector, route output, driver selector, and the
 * mini-map preview. The mini-map shows numbered markers for selected stops
 * and lets users click pins to toggle them — matching the fullscreen view.
 */

import { Clock, Expand } from 'lucide-react'
import { MapContainer, TileLayer, Marker, Polyline, Tooltip } from 'react-leaflet'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { RecenterMap, MapInteractionGuard } from '../MapShared'
import { UCSD_CENTER } from '../MapConstants'
import { Card, CardHeader, CardTitle, CardContent } from '../ui/card'
import { InfoToggleButton, InfoPanel } from '../InfoHelp'
import ErrorMessage from '../ErrorMessage'
import EditableOutput from '../EditableOutput'
import { SortableLocationList, ArrivalTimeSelector } from './routeBuilderShared'
import { LocationCombobox } from './LocationCombobox'
import { DriverSelector } from './DriverSelector'
import { createNumberedIcon, defaultMarkerIcon } from './numberedMarker'
import type { TimeModeKey } from './routeBuilderConstants'
import type { PickupLocationsResponse } from '../../types'
import { useUsernames } from '../../hooks/useUsernames'

export interface RouteBuilderWidgetProps {
    theme: string

    // Info panel
    showInfo: boolean
    onToggleInfo: () => void

    // Fullscreen
    onOpenFullscreen: () => void

    // Locations
    locationsData: PickupLocationsResponse | undefined
    locationsLoading: boolean
    selectedLocationKeys: string[]
    getLocationValue: (key: string) => string
    onToggleLocation: (key: string) => void
    onRemoveLocation: (index: number) => void
    onReorderLocations: (keys: string[]) => void

    // Time
    timeMode: TimeModeKey
    leaveTime: string
    onTimeModeChange: (mode: TimeModeKey, time: string) => void
    onLeaveTimeChange: (time: string) => void

    // Route
    routeLoading: boolean
    routeError: string
    routeOutput: string
    originalRouteOutput: string
    onChangeRouteOutput: (value: string) => void
    onCopyRoute: () => void
    onRevertRoute: () => void
    copied: boolean

    // Drivers
    drivers: string[]
    driverUsernameToName: Record<string, string>
    selectedDriver: string
    onSelectDriver: (driver: string) => void

    // Mini-map + trip metadata
    mapBounds: L.LatLngBoundsExpression | undefined
    routeGeometry: [number, number][] | null
    tripSummary: string | null
    legLabels: (string | null)[]
    lastToggledLocation: string | null
}

export function RouteBuilderWidget({
    theme,
    showInfo,
    onToggleInfo,
    onOpenFullscreen,
    locationsData,
    locationsLoading,
    selectedLocationKeys,
    getLocationValue,
    onToggleLocation,
    onRemoveLocation,
    onReorderLocations,
    timeMode,
    leaveTime,
    onTimeModeChange,
    onLeaveTimeChange,
    routeLoading,
    routeError,
    routeOutput,
    originalRouteOutput,
    onChangeRouteOutput,
    onCopyRoute,
    onRevertRoute,
    copied,
    drivers,
    driverUsernameToName,
    selectedDriver,
    onSelectDriver,
    mapBounds,
    routeGeometry,
    tripSummary,
    legLabels,
    lastToggledLocation,
}: RouteBuilderWidgetProps) {
    const { data: usernames } = useUsernames()
    const displayPrefix = selectedDriver ? `@${selectedDriver} drive: ` : ''
    const displayValue = displayPrefix + routeOutput
    const displayOriginal = displayPrefix + originalRouteOutput

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
                        onClick={onToggleInfo}
                        title="How to use Route Builder"
                    />
                    <button
                        onClick={onOpenFullscreen}
                        className="inline-flex items-center justify-center rounded-md p-1.5 text-slate-500 hover:text-slate-700 hover:bg-slate-100 dark:text-slate-400 dark:hover:text-slate-200 dark:hover:bg-zinc-800 transition-colors"
                        title="Open fullscreen map view"
                        aria-label="Open fullscreen map view"
                    >
                        <Expand className="h-4 w-4" />
                    </button>
                </div>
            </CardHeader>

            <CardContent>
                <InfoPanel
                    isOpen={showInfo}
                    onClose={() => onToggleInfo()}
                    title="How to use Route Builder"
                >
                    <ol className="list-decimal list-inside space-y-1.5">
                        <li>Pick stops from the dropdown — or click pins on the map below.</li>
                        <li>Drag stops to reorder them.</li>
                        <li>Set the arrival time at the final destination — the route generates automatically.</li>
                        <li>Optionally pick a driver, then copy the route into Discord.</li>
                    </ol>
                </InfoPanel>

                <div className="space-y-6">
                    {/* Location Combobox */}
                    <div>
                        <span className="text-sm font-medium text-slate-700 dark:text-slate-300 mb-2 block">
                            Select Locations
                        </span>
                        <LocationCombobox
                            locations={locationsData}
                            loading={locationsLoading}
                            selectedKeys={selectedLocationKeys}
                            onToggle={onToggleLocation}
                        />
                    </div>

                    {/* Selected Locations with Drag & Drop */}
                    {selectedLocationKeys.length > 0 && (
                        <div className="p-4 bg-slate-50 dark:bg-zinc-800/50 rounded-lg border border-slate-100 dark:border-zinc-700">
                            <div className="flex items-center justify-between gap-2 mb-3">
                                <div className="text-sm font-medium text-slate-700 dark:text-slate-300">
                                    Route Order ({selectedLocationKeys.length} location
                                    {selectedLocationKeys.length !== 1 ? 's' : ''})
                                </div>
                                {tripSummary && (
                                    <div
                                        className="inline-flex items-center gap-1.5 rounded-full bg-emerald-50 dark:bg-emerald-900/20 text-emerald-700 dark:text-emerald-300 px-2.5 py-1 text-xs font-medium"
                                        title="Estimated drive time and distance"
                                    >
                                        <Clock className="h-3 w-3" />
                                        {tripSummary}
                                    </div>
                                )}
                            </div>
                            <SortableLocationList
                                locationKeys={selectedLocationKeys}
                                getLocationValue={getLocationValue}
                                onRemove={onRemoveLocation}
                                onReorder={onReorderLocations}
                                legLabels={legLabels}
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
                            onTimeModeChange={onTimeModeChange}
                            onLeaveTimeChange={onLeaveTimeChange}
                            compact={false}
                        />
                    </div>

                    {/* Loading indicator */}
                    {routeLoading && (
                        <div className="flex items-center gap-2 text-sm text-slate-500 dark:text-slate-400">
                            <div className="h-4 w-4 animate-spin rounded-full border-2 border-emerald-500 border-t-transparent" />
                            Generating route…
                        </div>
                    )}
                </div>

                {/* Error Display */}
                <div className="mt-6">
                    <ErrorMessage message={routeError} />
                </div>

                {/* Driver selector */}
                {drivers.length > 0 && (
                    <div className="mt-6">
                        <DriverSelector
                            drivers={drivers}
                            driverUsernameToName={driverUsernameToName}
                            selectedDriver={selectedDriver}
                            onSelectDriver={onSelectDriver}
                        />
                    </div>
                )}

                {/* Route Output */}
                {routeOutput && (
                    <div className="mt-8 space-y-4 animate-in fade-in slide-in-from-bottom-4 duration-500">
                        <h3 className="text-lg font-semibold text-slate-900 dark:text-white">
                            Generated Route
                        </h3>
                        <EditableOutput
                            value={displayValue}
                            originalValue={displayOriginal}
                            onChange={(v) =>
                                onChangeRouteOutput(
                                    displayPrefix && v.startsWith(displayPrefix)
                                        ? v.slice(displayPrefix.length)
                                        : v
                                )
                            }
                            onCopy={onCopyRoute}
                            onRevert={onRevertRoute}
                            copied={copied}
                            usernames={usernames}
                        />
                    </div>
                )}

                {/* Static mini-map */}
                <div className="mt-6 rounded-lg overflow-hidden border border-slate-200 dark:border-zinc-700 relative z-0">
                    <MapContainer
                        center={UCSD_CENTER}
                        zoom={14}
                        scrollWheelZoom={false}
                        dragging={false}
                        className="h-52 sm:h-[350px] w-full"
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
                        <RecenterMap bounds={mapBounds} />

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
                                            ? createNumberedIcon(
                                                orderIndex + 1,
                                                lastToggledLocation === loc.key
                                            )
                                            : defaultMarkerIcon
                                    }
                                    eventHandlers={{
                                        click: (e) => {
                                            L.DomEvent.stopPropagation(e.originalEvent)
                                            onToggleLocation(loc.key)
                                        },
                                    }}
                                >
                                    <Tooltip direction="top" offset={[0, isSelected ? -10 : -36]}>
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
                </div>
            </CardContent>
        </Card>
    )
}
