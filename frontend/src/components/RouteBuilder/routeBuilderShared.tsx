/**
 * routeBuilderShared.tsx
 *
 * Shared building blocks used by both the page-level (full-screen map) and
 * component-level (card layout) RouteBuilder variants.
 *
 * Exports:
 *  - PRESET_TIMES            — single source of truth for time presets
 *  - TimeModeKey             — union type derived from PRESET_TIMES
 *  - SortableLocationItem    — drag-and-drop row for a single location
 *  - SortableLocationList    — DnD-context wrapper around a list of locations
 *  - ArrivalTimeSelector     — time preset buttons + optional custom input
 *  - useRouteGeometry        — hook that fetches OSRM route geometry
 */

import { X, GripVertical } from 'lucide-react'
import { PRESET_TIMES, type TimeModeKey } from './routeBuilderConstants'
import { Button } from '../ui/button'
import { Input } from '../ui/input'
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
// ---------------------------------------------------------------------------
// SortableLocationItem
// ---------------------------------------------------------------------------

export interface SortableLocationItemProps {
    id: string
    index: number
    locationValue: string
    onRemove: () => void
}

export function SortableLocationItem({
    id,
    index,
    locationValue,
    onRemove,
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

// ---------------------------------------------------------------------------
// SortableLocationList
// ---------------------------------------------------------------------------

export interface SortableLocationListProps {
    locationKeys: string[]
    getLocationValue: (key: string) => string
    onRemove: (index: number) => void
    onReorder: (keys: string[]) => void
}

export function SortableLocationList({
    locationKeys,
    getLocationValue,
    onRemove,
    onReorder,
}: SortableLocationListProps) {
    const sensors = useSensors(
        useSensor(PointerSensor, { activationConstraint: { distance: 8 } }),
        useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates })
    )

    const handleDragEnd = (event: DragEndEvent) => {
        const { active, over } = event
        if (over && active.id !== over.id) {
            const oldIndex = locationKeys.indexOf(active.id as string)
            const newIndex = locationKeys.indexOf(over.id as string)
            onReorder(arrayMove(locationKeys, oldIndex, newIndex))
        }
    }

    return (
        <DndContext
            sensors={sensors}
            collisionDetection={closestCenter}
            onDragEnd={handleDragEnd}
        >
            <SortableContext items={locationKeys} strategy={verticalListSortingStrategy}>
                <div className="space-y-2">
                    {locationKeys.map((key, index) => (
                        <SortableLocationItem
                            key={key}
                            id={key}
                            index={index}
                            locationValue={getLocationValue(key)}
                            onRemove={() => onRemove(index)}
                        />
                    ))}
                </div>
            </SortableContext>
        </DndContext>
    )
}

// ---------------------------------------------------------------------------
// ArrivalTimeSelector
// ---------------------------------------------------------------------------

export interface ArrivalTimeSelectorProps {
    timeMode: TimeModeKey
    leaveTime: string
    onTimeModeChange: (mode: TimeModeKey, time: string) => void
    onLeaveTimeChange: (time: string) => void
    /** compact=true renders small pill buttons (for overlay panels).
     *  compact=false renders full shadcn Button components (for card layouts). */
    compact?: boolean
}

export function ArrivalTimeSelector({
    timeMode,
    leaveTime,
    onTimeModeChange,
    onLeaveTimeChange,
    compact = false,
}: ArrivalTimeSelectorProps) {
    if (compact) {
        return (
            <div>
                <div className="flex flex-wrap gap-1.5">
                    {PRESET_TIMES.map((opt) => (
                        <button
                            key={opt.key}
                            type="button"
                            onClick={() => onTimeModeChange(opt.key, opt.time)}
                            className={`px-2.5 py-1 text-xs rounded-md border transition-colors ${timeMode === opt.key
                                ? 'bg-slate-900 text-white border-slate-900 dark:bg-white dark:text-slate-900 dark:border-white'
                                : 'bg-white text-slate-700 border-slate-200 hover:bg-slate-50 dark:bg-zinc-800 dark:text-slate-300 dark:border-zinc-600 dark:hover:bg-zinc-700'
                                }`}
                        >
                            {opt.shortLabel}
                        </button>
                    ))}
                </div>
                {timeMode === 'custom' && (
                    <Input
                        type="text"
                        value={leaveTime}
                        onChange={(e) => onLeaveTimeChange(e.target.value)}
                        placeholder="e.g., 7:10pm"
                        className="mt-2 h-8 text-sm"
                    />
                )}
            </div>
        )
    }

    return (
        <div>
            <div className="flex flex-wrap gap-2">
                {PRESET_TIMES.map((opt) => (
                    <Button
                        key={opt.key}
                        type="button"
                        variant={timeMode === opt.key ? 'default' : 'outline'}
                        onClick={() => onTimeModeChange(opt.key, opt.time)}
                    >
                        {opt.key === 'custom' ? 'Custom' : `${opt.label} (${opt.time})`}
                    </Button>
                ))}
            </div>
            {timeMode === 'custom' && (
                <div className="mt-3">
                    <Input
                        type="text"
                        value={leaveTime}
                        onChange={(e) => onLeaveTimeChange(e.target.value)}
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
    )
}
