/**
 * LocationsTable.tsx
 *
 * Table of all pickup locations — active rows with edit/toggle/delete
 * actions, inactive rows collapsed below with a Reactivate button. Clicking
 * a row pans the map to that location.
 */

import { MapPin, Pencil, Trash2, TriangleAlert } from 'lucide-react'
import { Button } from '../ui/button'
import { Switch } from '../ui/switch'
import { CollapsibleSection } from '../ui/collapsible'
import { SectionCard } from '../shared'
import type { ManagedPickupLocation } from '../../types'

interface LocationsTableProps {
    locations: ManagedPickupLocation[]
    unreachable: Set<string>
    onRowClick: (location: ManagedPickupLocation) => void
    onEdit: (location: ManagedPickupLocation) => void
    onToggleActive: (location: ManagedPickupLocation) => void
    onDelete: (location: ManagedPickupLocation) => void
    onAdd: () => void
}

function formatMinutes(value: number | null): string {
    return value != null ? `${value} min` : '—'
}

function LocationRow({
    location,
    unreachable,
    onRowClick,
    onEdit,
    onToggleActive,
    onDelete,
}: {
    location: ManagedPickupLocation
    unreachable: Set<string>
    onRowClick: (location: ManagedPickupLocation) => void
    onEdit: (location: ManagedPickupLocation) => void
    onToggleActive: (location: ManagedPickupLocation) => void
    onDelete: (location: ManagedPickupLocation) => void
}) {
    return (
        <tr
            className={`border-b border-border last:border-0 cursor-pointer transition-colors hover:bg-muted/50 ${location.is_active ? '' : 'opacity-60'}`}
            onClick={() => onRowClick(location)}
        >
            <td className="px-3 py-2">
                <div className="flex items-center gap-1.5 font-medium text-foreground">
                    {location.name}
                    {unreachable.has(location.name) && location.is_active && (
                        <span title="No route to destination — ride grouping will fail for this stop">
                            <TriangleAlert className="h-3.5 w-3.5 text-warning-text shrink-0" />
                        </span>
                    )}
                </div>
                {location.is_seeded && (
                    <span className="text-xs text-muted-foreground">default</span>
                )}
            </td>
            <td className="px-3 py-2 text-muted-foreground whitespace-nowrap tabular-nums">
                {location.latitude.toFixed(6)}, {location.longitude.toFixed(6)}
            </td>
            <td className="px-3 py-2 text-muted-foreground whitespace-nowrap">
                {formatMinutes(location.minutes_from_start)}
            </td>
            <td className="px-3 py-2 text-muted-foreground whitespace-nowrap">
                {formatMinutes(location.minutes_to_end)}
            </td>
            <td className="px-3 py-2" onClick={(e) => e.stopPropagation()}>
                <Switch
                    checked={location.is_active}
                    onCheckedChange={() => onToggleActive(location)}
                    aria-label={`${location.name} active`}
                />
            </td>
            <td className="px-3 py-2" onClick={(e) => e.stopPropagation()}>
                <div className="flex items-center gap-1">
                    <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => onEdit(location)}
                        title="Edit"
                    >
                        <Pencil className="h-4 w-4" />
                    </Button>
                    <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => onDelete(location)}
                        title="Delete"
                        className="text-destructive-text hover:text-destructive-text"
                    >
                        <Trash2 className="h-4 w-4" />
                    </Button>
                </div>
            </td>
        </tr>
    )
}

export function LocationsTable({
    locations,
    unreachable,
    onRowClick,
    onEdit,
    onToggleActive,
    onDelete,
    onAdd,
}: LocationsTableProps) {
    const active = locations.filter((loc) => loc.is_active)
    const inactive = locations.filter((loc) => !loc.is_active)

    const renderTable = (rows: ManagedPickupLocation[]) => (
        <div className="overflow-x-auto">
            <table className="w-full text-sm">
                <thead>
                    <tr className="border-b border-border text-left text-xs uppercase tracking-wide text-muted-foreground">
                        <th className="px-3 py-2 font-medium">Name</th>
                        <th className="px-3 py-2 font-medium">Coordinates</th>
                        <th className="px-3 py-2 font-medium">From dest.</th>
                        <th className="px-3 py-2 font-medium">To dest.</th>
                        <th className="px-3 py-2 font-medium">Active</th>
                        <th className="px-3 py-2 font-medium">Actions</th>
                    </tr>
                </thead>
                <tbody>
                    {rows.map((location) => (
                        <LocationRow
                            key={location.id}
                            location={location}
                            unreachable={unreachable}
                            onRowClick={onRowClick}
                            onEdit={onEdit}
                            onToggleActive={onToggleActive}
                            onDelete={onDelete}
                        />
                    ))}
                </tbody>
            </table>
        </div>
    )

    return (
        <SectionCard
            icon={<MapPin className="h-4 w-4" />}
            title="Pickup Locations"
            actions={
                <Button size="sm" onClick={onAdd}>
                    Add location
                </Button>
            }
        >
            {active.length > 0 ? (
                renderTable(active)
            ) : (
                <p className="text-sm text-muted-foreground py-4 text-center">
                    No active locations.
                </p>
            )}

            {inactive.length > 0 && (
                <div className="mt-4">
                    <CollapsibleSection title={`Inactive (${inactive.length})`}>
                        {renderTable(inactive)}
                    </CollapsibleSection>
                </div>
            )}
        </SectionCard>
    )
}
