import { useState, useEffect } from 'react'
import { getAutomaticDay } from '../lib/utils'
import { apiFetch } from '../lib/api'
import { Button } from './ui/button'
import { Input } from './ui/input'
import { Select } from './ui/select'
import { InfoToggleButton, InfoPanel } from './InfoHelp'
import ErrorMessage from './ErrorMessage'
import EditableOutput from './EditableOutput'
import type { PickupLocationsResponse, MakeRouteResponse } from '../types'

import { Card, CardHeader, CardTitle, CardContent } from './ui/card'
import { X, GripVertical } from 'lucide-react'

import {
    DndContext,
    closestCenter,
    KeyboardSensor,
    PointerSensor,
    useSensor,
    useSensors,
} from '@dnd-kit/core'
import type { DragEndEvent } from '@dnd-kit/core'
import {
    arrayMove,
    SortableContext,
    sortableKeyboardCoordinates,
    useSortable,
    verticalListSortingStrategy,
} from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'

// Sortable item component for drag-and-drop
interface SortableLocationItemProps {
    id: string
    index: number
    locationKey: string
    locationValue: string
    onRemove: () => void
}

function SortableLocationItem({
    id,
    index,
    locationValue,
    onRemove
}: SortableLocationItemProps) {
    const {
        attributes,
        listeners,
        setNodeRef,
        transform,
        transition,
        isDragging,
    } = useSortable({ id })

    const style = {
        transform: CSS.Transform.toString(transform),
        transition,
        opacity: isDragging ? 0.5 : 1,
    }

    return (
        <div
            ref={setNodeRef}
            style={style}
            className="flex items-center gap-2 px-3 py-2 bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-700 rounded-md transition-all"
        >
            <div
                {...attributes}
                {...listeners}
                className="cursor-grab active:cursor-grabbing touch-none"
            >
                <GripVertical className="h-4 w-4 text-slate-400" />
            </div>
            <span className="flex-1 text-sm text-slate-900 dark:text-slate-100">
                {index + 1}. {locationValue}
            </span>
            <button
                type="button"
                onClick={onRemove}
                className="text-slate-400 hover:text-red-500 transition-colors"
                title="Remove location"
            >
                <X className="h-4 w-4" />
            </button>
        </div>
    )
}

function RouteBuilder() {
    // State for available locations from API
    const [availableLocations, setAvailableLocations] = useState<PickupLocationsResponse | null>(null)
    const [locationsLoading, setLocationsLoading] = useState(true)

    // State for location selection dropdown
    const [selectedLocation, setSelectedLocation] = useState<string>('')

    // State for selected locations - store keys (e.g., "SEVENTH") not full names
    const [selectedLocationKeys, setSelectedLocationKeys] = useState<string[]>([])

    const defaultTimes: Record<'friday' | 'sunday', string> = {
        friday: '7:10pm',
        sunday: '10:10am',
    }

    const autoMode = getAutomaticDay()

    // State for leave time
    const [leaveTime, setLeaveTime] = useState(defaultTimes[autoMode])
    const [timeMode, setTimeMode] = useState<'friday' | 'sunday' | 'custom'>(autoMode)


    // State for route output
    const [routeOutput, setRouteOutput] = useState<string>('')
    const [originalRouteOutput, setOriginalRouteOutput] = useState<string>('')
    const [routeLoading, setRouteLoading] = useState(false)
    const [routeError, setRouteError] = useState<string>('')
    const [copiedRoute, setCopiedRoute] = useState(false)

    // UI State
    const [showInfo, setShowInfo] = useState(false)

    // Drag and drop sensors
    const sensors = useSensors(
        useSensor(PointerSensor, {
            activationConstraint: {
                distance: 8, // 8px of movement required before drag starts
            },
        }),
        useSensor(KeyboardSensor, {
            coordinateGetter: sortableKeyboardCoordinates,
        })
    )

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
    const getLocationValue = (key: string): string => {
        return availableLocations?.locations.find(loc => loc.key === key)?.value || key
    }

    // Add location to selected list from dropdown
    const addLocation = () => {
        if (selectedLocation && !selectedLocationKeys.includes(selectedLocation)) {
            setSelectedLocationKeys([...selectedLocationKeys, selectedLocation])
            setSelectedLocation('') // Reset dropdown
        }
    }

    // Remove location from selected list
    const removeLocation = (index: number) => {
        setSelectedLocationKeys(selectedLocationKeys.filter((_, i) => i !== index))
    }

    // Handle drag end event
    const handleDragEnd = (event: DragEndEvent) => {
        const { active, over } = event

        if (over && active.id !== over.id) {
            setSelectedLocationKeys((items) => {
                const oldIndex = items.indexOf(active.id as string)
                const newIndex = items.indexOf(over.id as string)
                return arrayMove(items, oldIndex, newIndex)
            })
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
                    leave_time: leaveTime
                })
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
                                    onChange={(e) => setSelectedLocation(e.target.value)}
                                    disabled={locationsLoading}
                                    className="flex-1"
                                >
                                    <option value="">
                                        {locationsLoading ? 'Loading locations...' : 'Choose a location...'}
                                    </option>
                                    {availableLocations?.locations
                                        .filter(loc => !selectedLocationKeys.includes(loc.key))
                                        .map((location) => (
                                            <option key={location.key} value={location.key}>
                                                {location.value}
                                            </option>
                                        ))}
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
                                Route Order ({selectedLocationKeys.length} location{selectedLocationKeys.length !== 1 ? 's' : ''})
                            </div>
                            <DndContext
                                sensors={sensors}
                                collisionDetection={closestCenter}
                                onDragEnd={handleDragEnd}
                            >
                                <SortableContext
                                    items={selectedLocationKeys}
                                    strategy={verticalListSortingStrategy}
                                >
                                    <div className="space-y-2">
                                        {selectedLocationKeys.map((locationKey, index) => (
                                            <SortableLocationItem
                                                key={locationKey}
                                                id={locationKey}
                                                index={index}
                                                locationKey={locationKey}
                                                locationValue={getLocationValue(locationKey)}
                                                onRemove={() => removeLocation(index)}
                                            />
                                        ))}
                                    </div>
                                </SortableContext>
                            </DndContext>
                        </div>
                    )}

                    {/* Arrival Time Selection */}
                    <div>
                        <span className="text-sm font-medium text-slate-700 dark:text-slate-300 mb-2 block">
                            Arrival Time at Final Destination
                        </span>
                        <div className="flex flex-wrap gap-2">
                            <Button
                                type="button"
                                variant={timeMode === 'friday' ? 'default' : 'outline'}
                                onClick={() => {
                                    setTimeMode('friday')
                                    setLeaveTime('7:10pm')
                                }}
                            >
                                Friday Fellowship (7:10pm)
                            </Button>
                            <Button
                                type="button"
                                variant={timeMode === 'sunday' ? 'default' : 'outline'}
                                onClick={() => {
                                    setTimeMode('sunday')
                                    setLeaveTime('10:10am')
                                }}
                            >
                                Sunday Service (10:10am)
                            </Button>
                            <Button
                                type="button"
                                variant={timeMode === 'custom' ? 'default' : 'outline'}
                                onClick={() => {
                                    setTimeMode('custom')
                                    setLeaveTime('')
                                }}
                            >
                                Custom
                            </Button>
                        </div>
                        {timeMode === 'custom' && (
                            <div className="mt-3">
                                <Input
                                    type="text"
                                    value={leaveTime}
                                    onChange={(e) => setLeaveTime(e.target.value)}
                                    placeholder="e.g., 7:10pm, 7p, 19:10"
                                    required
                                    className="w-full max-w-md"
                                />
                                <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
                                    Supports formats: "7:10pm", "7p", "19:10"
                                </p>
                            </div>
                        )}
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
            </CardContent>
        </Card>
    )
}

export default RouteBuilder
