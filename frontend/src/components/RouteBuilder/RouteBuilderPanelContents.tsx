/**
 * RouteBuilderPanelContents.tsx
 *
 * The scrollable body of the Route Builder control panel — shared between the
 * desktop side panel (RouteBuilderDesktopPanel) and the mobile bottom sheet
 * (RouteBuilderMobileSheet).
 *
 * Shows either an empty-state prompt or the full route-building controls:
 * sortable location list, arrival time selector, generate button, error, and
 * route output.
 */

import { MousePointerClick } from 'lucide-react'
import { Button } from '../ui/button'
import { SortableLocationList, ArrivalTimeSelector } from './routeBuilderShared'
import type { TimeModeKey } from './routeBuilderShared'
import EditableOutput from '../EditableOutput'

export interface RouteBuilderPanelContentsProps {
    // Location state
    selectedLocationKeys: string[]
    getLocationValue: (key: string) => string
    onRemoveLocation: (index: number) => void
    onReorderLocations: (keys: string[]) => void
    onClearAll: () => void

    // Time state
    timeMode: TimeModeKey
    leaveTime: string
    onTimeModeChange: (mode: TimeModeKey, time: string) => void
    onLeaveTimeChange: (time: string) => void

    // Route state
    routeLoading: boolean
    routeError: string
    routeOutput: string
    originalRouteOutput: string
    onGenerateRoute: () => void
    onChangeRouteOutput: (value: string) => void
    onCopyRoute: () => void
    onRevertRoute: () => void
    copied: boolean
}

export function RouteBuilderPanelContents({
    selectedLocationKeys,
    getLocationValue,
    onRemoveLocation,
    onReorderLocations,
    onClearAll,
    timeMode,
    leaveTime,
    onTimeModeChange,
    onLeaveTimeChange,
    routeLoading,
    routeError,
    routeOutput,
    originalRouteOutput,
    onGenerateRoute,
    onChangeRouteOutput,
    onCopyRoute,
    onRevertRoute,
    copied,
}: RouteBuilderPanelContentsProps) {
    if (selectedLocationKeys.length === 0) {
        return (
            <div className="flex flex-col items-center text-center py-4">
                <div className="w-12 h-12 rounded-full bg-emerald-50 dark:bg-emerald-900/30 flex items-center justify-center mb-3">
                    <MousePointerClick className="h-6 w-6 text-emerald-600 dark:text-emerald-400" />
                </div>
                <div className="text-sm font-semibold text-slate-900 dark:text-white mb-1">
                    Tap pins to build your route
                </div>
                <p className="text-xs text-slate-500 dark:text-slate-400 leading-relaxed">
                    Tap on map markers to add stops. Selected pins turn{' '}
                    <span className="text-emerald-600 dark:text-emerald-400 font-medium">green</span>{' '}
                    and are numbered in order.
                </p>
            </div>
        )
    }

    return (
        <>
            {/* Route order header + clear */}
            <div className="flex items-center justify-between mb-3">
                <div className="text-sm font-semibold text-slate-700 dark:text-slate-300">
                    Route Order ({selectedLocationKeys.length} location
                    {selectedLocationKeys.length !== 1 ? 's' : ''})
                </div>
                <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={onClearAll}
                    className="h-6 px-2 text-xs text-slate-500 hover:text-red-600 dark:text-slate-400 dark:hover:text-red-400"
                >
                    Clear All
                </Button>
            </div>

            <SortableLocationList
                locationKeys={selectedLocationKeys}
                getLocationValue={getLocationValue}
                onRemove={onRemoveLocation}
                onReorder={onReorderLocations}
            />

            {/* Arrival Time */}
            <div className="mt-4 pt-4 border-t border-slate-200 dark:border-zinc-700">
                <div className="text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                    Arrival Time
                </div>
                <ArrivalTimeSelector
                    timeMode={timeMode}
                    leaveTime={leaveTime}
                    onTimeModeChange={onTimeModeChange}
                    onLeaveTimeChange={onLeaveTimeChange}
                    compact={true}
                />
            </div>

            {/* Generate */}
            <Button
                onClick={onGenerateRoute}
                disabled={routeLoading || selectedLocationKeys.length === 0 || !leaveTime}
                className="w-full mt-3"
            >
                {routeLoading ? 'Generating...' : 'Generate Route'}
            </Button>

            {/* Error */}
            {routeError && (
                <div className="mt-2 text-xs text-red-600 dark:text-red-400">{routeError}</div>
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
                        onChange={onChangeRouteOutput}
                        onCopy={onCopyRoute}
                        onRevert={onRevertRoute}
                        copied={copied}
                        minHeight="min-h-[120px]"
                    />
                </div>
            )}
        </>
    )
}
