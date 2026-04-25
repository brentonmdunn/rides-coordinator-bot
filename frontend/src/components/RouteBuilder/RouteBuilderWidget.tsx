/**
 * RouteBuilderWidget.tsx
 *
 * The card / widget view of the Route Builder — the default display when not
 * in fullscreen mode. Contains the location dropdown, sortable stop list,
 * arrival time selector, error message, route output, and the static
 * mini-map preview. Route is generated automatically as locations change.
 */

import { Expand } from 'lucide-react'
import { MapContainer, TileLayer, Marker, Popup, Polyline } from 'react-leaflet'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { RecenterMap, MapInteractionGuard } from '../MapShared'
import { UCSD_CENTER } from '../MapConstants'
import { Card, CardHeader, CardTitle, CardContent } from '../ui/card'
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from '../ui/select'
import { Button } from '../ui/button'
import { InfoToggleButton, InfoPanel } from '../InfoHelp'
import ErrorMessage from '../ErrorMessage'
import EditableOutput from '../EditableOutput'
import { SortableLocationList, ArrivalTimeSelector } from './routeBuilderShared'
import type { TimeModeKey } from './routeBuilderConstants'
import type { PickupLocationsResponse } from '../../types'

export interface RouteBuilderWidgetProps {
    theme: string

    // Info panel
    showInfo: boolean
    onToggleInfo: () => void

    // Fullscreen
    onOpenFullscreen: () => void

    // Location dropdown
    locationsData: PickupLocationsResponse | undefined
    locationsLoading: boolean
    selectedLocation: string
    onSelectLocation: (key: string) => void
    selectedLocationKeys: string[]
    getLocationValue: (key: string) => string
    onAddLocation: () => void
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

    // Mini-map
    mapBounds: L.LatLngBoundsExpression | undefined
    routeGeometry: [number, number][] | null
}

export function RouteBuilderWidget({
    theme,
    showInfo,
    onToggleInfo,
    onOpenFullscreen,
    locationsData,
    locationsLoading,
    selectedLocation,
    onSelectLocation,
    selectedLocationKeys,
    getLocationValue,
    onAddLocation,
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
    mapBounds,
    routeGeometry,
}: RouteBuilderWidgetProps) {
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
                        <li>Select pickup locations from the dropdown in the order you want to visit them.</li>
                        <li>Drag locations to reorder them if needed.</li>
                        <li>Enter the final destination arrival time — the route generates automatically.</li>
                        <li>Copy the route and paste it into Discord.</li>
                    </ol>
                </InfoPanel>

                <div className="space-y-6">
                    {/* Location Selection Dropdown */}
                    <div>
                        <label className="block">
                            <span className="text-sm font-medium text-slate-700 dark:text-slate-300 mb-2 block">
                                Select Locations
                            </span>
                            <div className="flex gap-2">
                                <Select
                                    value={selectedLocation}
                                    onValueChange={onSelectLocation}
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
                                    onClick={onAddLocation}
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
                                onRemove={onRemoveLocation}
                                onReorder={onReorderLocations}
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

                {/* Route Output */}
                {routeOutput && (
                    <div className="mt-8 space-y-4 animate-in fade-in slide-in-from-bottom-4 duration-500">
                        <h3 className="text-lg font-semibold text-slate-900 dark:text-white">
                            Generated Route
                        </h3>
                        <EditableOutput
                            value={routeOutput}
                            originalValue={originalRouteOutput}
                            onChange={onChangeRouteOutput}
                            onCopy={onCopyRoute}
                            onRevert={onRevertRoute}
                            copied={copied}
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
    )
}
