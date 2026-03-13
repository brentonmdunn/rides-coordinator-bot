import { useState, useCallback, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { MapContainer, TileLayer, Marker, Tooltip, Polyline, useMapEvents } from 'react-leaflet'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import '@luomus/leaflet-smooth-wheel-zoom'
import { UCSD_CENTER, setupLeafletIcons } from '../components/MapShared'
import { apiFetch } from '../lib/api'
import type { PickupLocationsResponse, MakeRouteResponse } from '../types'
import { X, GripVertical } from 'lucide-react'
import { Button } from '../components/ui/button'
import { Input } from '../components/ui/input'
import EditableOutput from '../components/EditableOutput'
import { getAutomaticDay, useCopyToClipboard } from '../lib/utils'

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

// --- Sortable drag-and-drop item ---
interface SortableLocationItemProps {
    id: string
    index: number
    locationValue: string
    onRemove: () => void
}

function SortableLocationItem({ id, index, locationValue, onRemove }: SortableLocationItemProps) {
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
    const [routeGeometry, setRouteGeometry] = useState<[number, number][] | null>(null)

    const defaultTimes: Record<'friday' | 'sunday', string> = {
        friday: '7:10pm',
        sunday: '10:10am',
    }
    const autoMode = getAutomaticDay()
    const [leaveTime, setLeaveTime] = useState(defaultTimes[autoMode])
    const [timeMode, setTimeMode] = useState<'friday' | 'sunday' | 'sunday_class' | 'discipleship' | 'custom'>(autoMode)

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

    const removeLocation = (index: number) => {
        setSelectedLocationKeys((prev) => prev.filter((_, i) => i !== index))
    }

    // Drag and drop sensors
    const sensors = useSensors(
        useSensor(PointerSensor, {
            activationConstraint: { distance: 8 },
        }),
        useSensor(KeyboardSensor, {
            coordinateGetter: sortableKeyboardCoordinates,
        })
    )

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

    // Fetch route geometry from OSRM when selected locations change
    useEffect(() => {
        if (!locationsData || selectedLocationKeys.length < 2) {
            setRouteGeometry(null)
            return
        }

        const coords = selectedLocationKeys
            .map((key) => {
                const name = getLocationValue(key)
                return locationsData.coordinates[name]
            })
            .filter(Boolean)

        if (coords.length < 2) {
            setRouteGeometry(null)
            return
        }

        const coordsString = coords.map((c) => `${c.lng},${c.lat}`).join(';')

        const fetchRoute = async () => {
            try {
                const res = await fetch(
                    `https://router.project-osrm.org/route/v1/driving/${coordsString}?overview=full&geometries=geojson`
                )
                if (!res.ok) return
                const data = await res.json()
                if (data.routes && data.routes.length > 0) {
                    const feature = data.routes[0].geometry
                    const latLngs = feature.coordinates.map(
                        (c: [number, number]) => [c[1], c[0]] as [number, number]
                    )
                    setRouteGeometry(latLngs)
                }
            } catch (err) {
                console.error('Failed to fetch route geometry', err)
            }
        }

        fetchRoute()
    }, [selectedLocationKeys, locationsData, getLocationValue])

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
                        <div className="text-sm font-semibold text-slate-700 dark:text-slate-300 mb-3">
                            Route Order ({selectedLocationKeys.length} location
                            {selectedLocationKeys.length !== 1 ? 's' : ''})
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
                                            locationValue={getLocationValue(locationKey)}
                                            onRemove={() => removeLocation(index)}
                                        />
                                    ))}
                                </div>
                            </SortableContext>
                        </DndContext>

                        {/* Arrival Time Selection */}
                        <div className="mt-4 pt-4 border-t border-slate-200 dark:border-zinc-700">
                            <div className="text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                                Arrival Time
                            </div>
                            <div className="flex flex-wrap gap-1.5">
                                {[
                                    { key: 'friday' as const, label: 'Fri (7:10pm)', time: '7:10pm' },
                                    { key: 'sunday' as const, label: 'Sun (10:10am)', time: '10:10am' },
                                    { key: 'sunday_class' as const, label: 'Class (8:40am)', time: '8:40am' },
                                    { key: 'discipleship' as const, label: 'Disc (7:10am)', time: '7:10am' },
                                    { key: 'custom' as const, label: 'Custom', time: '' },
                                ].map((opt) => (
                                    <button
                                        key={opt.key}
                                        type="button"
                                        onClick={() => {
                                            setTimeMode(opt.key)
                                            setLeaveTime(opt.time)
                                        }}
                                        className={`px-2.5 py-1 text-xs rounded-md border transition-colors ${
                                            timeMode === opt.key
                                                ? 'bg-slate-900 text-white border-slate-900 dark:bg-white dark:text-slate-900 dark:border-white'
                                                : 'bg-white text-slate-700 border-slate-200 hover:bg-slate-50 dark:bg-zinc-800 dark:text-slate-300 dark:border-zinc-600 dark:hover:bg-zinc-700'
                                        }`}
                                    >
                                        {opt.label}
                                    </button>
                                ))}
                            </div>
                            {timeMode === 'custom' && (
                                <Input
                                    type="text"
                                    value={leaveTime}
                                    onChange={(e) => setLeaveTime(e.target.value)}
                                    placeholder="e.g., 7:10pm"
                                    className="mt-2 h-8 text-sm"
                                />
                            )}
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
