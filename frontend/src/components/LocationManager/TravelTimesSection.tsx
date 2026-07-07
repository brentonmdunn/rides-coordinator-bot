/**
 * TravelTimesSection.tsx
 *
 * Non-map editor for travel-time edges: a list of "A ↔ B — n min" rows with
 * inline minute editing and deletion, plus an add form with two location
 * selects. Times are 100% user-entered — there is deliberately no
 * routing-engine suggestion anywhere.
 */

import { useState } from 'react'
import { Check, Clock, Pencil, Trash2, X } from 'lucide-react'
import { Button } from '../ui/button'
import { Input } from '../ui/input'
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from '../ui/select'
import { SectionCard } from '../shared'
import type { ManagedPickupLocation, PickupLocationEdge } from '../../types'
import type { EdgeInput } from './useLocationManager'

interface TravelTimesSectionProps {
    locations: ManagedPickupLocation[]
    edges: PickupLocationEdge[]
    submitting: boolean
    onUpsert: (input: EdgeInput) => void
    onDelete: (edgeId: number) => void
}

function isValidMinutes(raw: string): boolean {
    const value = Number(raw.trim())
    return raw.trim() !== '' && Number.isInteger(value) && value > 0
}

export function TravelTimesSection({
    locations,
    edges,
    submitting,
    onUpsert,
    onDelete,
}: TravelTimesSectionProps) {
    const [editingEdgeId, setEditingEdgeId] = useState<number | null>(null)
    const [editMinutes, setEditMinutes] = useState('')
    const [newA, setNewA] = useState('')
    const [newB, setNewB] = useState('')
    const [newMinutes, setNewMinutes] = useState('')

    const nameById = new Map(locations.map((loc) => [loc.id, loc.name]))
    const activeLocations = locations.filter((loc) => loc.is_active)

    const sortedEdges = [...edges].sort((a, b) => {
        const nameA = nameById.get(a.location_a_id) ?? ''
        const nameB = nameById.get(b.location_a_id) ?? ''
        return nameA.localeCompare(nameB)
    })

    const startEditing = (edge: PickupLocationEdge) => {
        setEditingEdgeId(edge.id)
        setEditMinutes(String(edge.minutes))
    }

    const saveEdit = (edge: PickupLocationEdge) => {
        if (!isValidMinutes(editMinutes)) return
        onUpsert({
            location_a_id: edge.location_a_id,
            location_b_id: edge.location_b_id,
            minutes: Number(editMinutes.trim()),
        })
        setEditingEdgeId(null)
    }

    const canAdd =
        newA !== '' && newB !== '' && newA !== newB && isValidMinutes(newMinutes)

    const handleAdd = () => {
        if (!canAdd) return
        onUpsert({
            location_a_id: Number(newA),
            location_b_id: Number(newB),
            minutes: Number(newMinutes.trim()),
        })
        setNewA('')
        setNewB('')
        setNewMinutes('')
    }

    return (
        <SectionCard icon={<Clock className="h-4 w-4" />} title="Travel Times">
            <p className="text-sm text-muted-foreground mb-4">
                Driving minutes between directly connected stops. Pairs without a direct
                connection use the shortest path through these. All values are entered by
                hand — measure what the drive actually takes, including the stop itself.
            </p>

            {sortedEdges.length === 0 ? (
                <p className="text-sm text-muted-foreground py-4 text-center">
                    No travel times yet — add one below or connect two markers on the map.
                </p>
            ) : (
                <ul className="divide-y divide-border rounded-lg border border-border">
                    {sortedEdges.map((edge) => {
                        const isEditing = editingEdgeId === edge.id
                        return (
                            <li
                                key={edge.id}
                                className="flex items-center justify-between gap-3 px-3 py-2 text-sm"
                            >
                                <span className="min-w-0 text-foreground">
                                    {nameById.get(edge.location_a_id) ?? `#${edge.location_a_id}`}
                                    <span className="text-muted-foreground"> ↔ </span>
                                    {nameById.get(edge.location_b_id) ?? `#${edge.location_b_id}`}
                                </span>
                                <span className="flex items-center gap-1 shrink-0">
                                    {isEditing ? (
                                        <>
                                            <Input
                                                inputMode="numeric"
                                                value={editMinutes}
                                                onChange={(e) => setEditMinutes(e.target.value)}
                                                onKeyDown={(e) => {
                                                    if (e.key === 'Enter') saveEdit(edge)
                                                    if (e.key === 'Escape') setEditingEdgeId(null)
                                                }}
                                                className="h-8 w-16 text-right"
                                                autoFocus
                                            />
                                            <Button
                                                variant="ghost"
                                                size="icon"
                                                onClick={() => saveEdit(edge)}
                                                disabled={submitting || !isValidMinutes(editMinutes)}
                                                title="Save"
                                            >
                                                <Check className="h-4 w-4" />
                                            </Button>
                                            <Button
                                                variant="ghost"
                                                size="icon"
                                                onClick={() => setEditingEdgeId(null)}
                                                title="Cancel"
                                            >
                                                <X className="h-4 w-4" />
                                            </Button>
                                        </>
                                    ) : (
                                        <>
                                            <span className="text-muted-foreground tabular-nums">
                                                {edge.minutes} min
                                            </span>
                                            <Button
                                                variant="ghost"
                                                size="icon"
                                                onClick={() => startEditing(edge)}
                                                title="Edit minutes"
                                            >
                                                <Pencil className="h-4 w-4" />
                                            </Button>
                                            <Button
                                                variant="ghost"
                                                size="icon"
                                                onClick={() => onDelete(edge.id)}
                                                disabled={submitting}
                                                title="Delete"
                                                className="text-destructive-text hover:text-destructive-text"
                                            >
                                                <Trash2 className="h-4 w-4" />
                                            </Button>
                                        </>
                                    )}
                                </span>
                            </li>
                        )
                    })}
                </ul>
            )}

            <div className="mt-4 flex flex-col sm:flex-row gap-2 sm:items-end">
                <div className="flex-1 space-y-1.5">
                    <label className="text-sm font-medium text-foreground">From</label>
                    <Select value={newA} onValueChange={setNewA}>
                        <SelectTrigger>
                            <SelectValue placeholder="Select location" />
                        </SelectTrigger>
                        <SelectContent>
                            {activeLocations.map((loc) => (
                                <SelectItem key={loc.id} value={String(loc.id)}>
                                    {loc.name}
                                </SelectItem>
                            ))}
                        </SelectContent>
                    </Select>
                </div>
                <div className="flex-1 space-y-1.5">
                    <label className="text-sm font-medium text-foreground">To</label>
                    <Select value={newB} onValueChange={setNewB}>
                        <SelectTrigger>
                            <SelectValue placeholder="Select location" />
                        </SelectTrigger>
                        <SelectContent>
                            {activeLocations
                                .filter((loc) => String(loc.id) !== newA)
                                .map((loc) => (
                                    <SelectItem key={loc.id} value={String(loc.id)}>
                                        {loc.name}
                                    </SelectItem>
                                ))}
                        </SelectContent>
                    </Select>
                </div>
                <div className="w-full sm:w-28 space-y-1.5">
                    <label className="text-sm font-medium text-foreground">Minutes</label>
                    <Input
                        inputMode="numeric"
                        value={newMinutes}
                        onChange={(e) => setNewMinutes(e.target.value)}
                        onKeyDown={(e) => { if (e.key === 'Enter') handleAdd() }}
                        placeholder="3"
                    />
                </div>
                <Button onClick={handleAdd} disabled={!canAdd || submitting}>
                    Add
                </Button>
            </div>
        </SectionCard>
    )
}
