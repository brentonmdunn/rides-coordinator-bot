/**
 * LocationManager.tsx
 *
 * Composition root for the Locations management page — the interactive map
 * plus the locations table, travel-times editor and settings sections. Owns
 * all page-level UI state (map mode, dialogs, pan target).
 */

import { useMemo, useState } from 'react'
import { MapPin, Spline, TriangleAlert, X } from 'lucide-react'
import { Button } from '../ui/button'
import { Switch } from '../ui/switch'
import { SectionCard } from '../shared'
import ErrorMessage from '../ErrorMessage'
import { GridSkeleton } from '../LoadingSkeleton'
import { ConfirmDialog } from '../ConfirmDialog'
import { useTheme } from '../use-theme'
import { setupLeafletIcons } from '../MapConstants'
import { useLocationManager } from './useLocationManager'
import { LocationsMap, type MapMode } from './LocationsMap'
import { LocationsTable } from './LocationsTable'
import { TravelTimesSection } from './TravelTimesSection'
import { SettingsSection } from './SettingsSection'
import { LocationFormDialog, type LocationFormState } from './LocationFormDialog'
import { EdgeDialog, type EdgeDialogState } from './EdgeDialog'
import type { ManagedPickupLocation, PickupLocationEdge } from '../../types'

setupLeafletIcons()

const MODE_HINTS: Record<MapMode, string | null> = {
    view: null,
    'add-location': 'Click anywhere on the map to place the new location.',
    'add-edge': 'Click two markers in sequence to connect them with a travel time.',
}

function normalizedPair(aId: number, bId: number): [number, number] {
    return aId < bId ? [aId, bId] : [bId, aId]
}

function LocationManager() {
    const { theme } = useTheme()
    const manager = useLocationManager()
    const { data, isLoading, error } = manager.query

    const [mode, setMode] = useState<MapMode>('view')
    const [pendingEdgeStartId, setPendingEdgeStartId] = useState<number | null>(null)
    const [showInactive, setShowInactive] = useState(false)
    const [flyTarget, setFlyTarget] = useState<[number, number] | undefined>(undefined)
    const [locationForm, setLocationForm] = useState<LocationFormState | null>(null)
    const [edgeDialog, setEdgeDialog] = useState<EdgeDialogState | null>(null)
    const [deleteTarget, setDeleteTarget] = useState<ManagedPickupLocation | null>(null)

    const locations = useMemo(() => data?.locations ?? [], [data])
    const edges = data?.edges ?? []
    const unreachable = useMemo(() => new Set(data?.unreachable ?? []), [data])
    const locationsById = useMemo(
        () => new Map(locations.map((loc) => [loc.id, loc])),
        [locations]
    )

    const switchMode = (next: MapMode) => {
        setMode((current) => (current === next ? 'view' : next))
        setPendingEdgeStartId(null)
    }

    const handleMapClick = (latitude: number, longitude: number) => {
        setLocationForm({ location: null, prefill: { latitude, longitude } })
        setMode('view')
    }

    const handleMarkerClick = (location: ManagedPickupLocation) => {
        if (mode !== 'add-edge') return
        if (pendingEdgeStartId == null) {
            setPendingEdgeStartId(location.id)
            return
        }
        if (pendingEdgeStartId === location.id) {
            setPendingEdgeStartId(null)
            return
        }
        const start = locationsById.get(pendingEdgeStartId)
        if (!start) {
            setPendingEdgeStartId(null)
            return
        }
        const [aId, bId] = normalizedPair(start.id, location.id)
        const existing = edges.find(
            (edge) =>
                normalizedPair(edge.location_a_id, edge.location_b_id)[0] === aId &&
                normalizedPair(edge.location_a_id, edge.location_b_id)[1] === bId
        )
        setEdgeDialog({
            locationAId: aId,
            locationBId: bId,
            locationAName: locationsById.get(aId)?.name ?? `#${aId}`,
            locationBName: locationsById.get(bId)?.name ?? `#${bId}`,
            minutes: existing?.minutes ?? null,
            edgeId: existing?.id ?? null,
        })
        setPendingEdgeStartId(null)
        setMode('view')
    }

    const handleEdgeClick = (edge: PickupLocationEdge) => {
        setEdgeDialog({
            locationAId: edge.location_a_id,
            locationBId: edge.location_b_id,
            locationAName: locationsById.get(edge.location_a_id)?.name ?? `#${edge.location_a_id}`,
            locationBName: locationsById.get(edge.location_b_id)?.name ?? `#${edge.location_b_id}`,
            minutes: edge.minutes,
            edgeId: edge.id,
        })
    }

    const handleLocationSubmit = (input: Parameters<typeof manager.createLocation.mutate>[0]) => {
        if (locationForm?.location) {
            manager.updateLocation.mutate(
                { id: locationForm.location.id, patch: input },
                { onSuccess: () => setLocationForm(null) }
            )
        } else {
            manager.createLocation.mutate(input, { onSuccess: () => setLocationForm(null) })
        }
    }

    const handleToggleActive = (location: ManagedPickupLocation) => {
        manager.updateLocation.mutate({
            id: location.id,
            patch: { is_active: !location.is_active },
        })
    }

    const handleEdgeSave = (minutes: number) => {
        if (!edgeDialog) return
        manager.upsertEdge.mutate(
            {
                location_a_id: edgeDialog.locationAId,
                location_b_id: edgeDialog.locationBId,
                minutes,
            },
            { onSuccess: () => setEdgeDialog(null) }
        )
    }

    const handleEdgeDelete = (edgeId: number) => {
        manager.deleteEdge.mutate(edgeId, { onSuccess: () => setEdgeDialog(null) })
    }

    if (isLoading) {
        return <GridSkeleton count={6} />
    }

    if (error) {
        return <ErrorMessage message={error instanceof Error ? error.message : 'Failed to load locations'} />
    }

    if (!data) return null

    const activeUnreachable = locations.filter(
        (loc) => loc.is_active && unreachable.has(loc.name)
    )

    return (
        <div className="space-y-8">
            <SectionCard
                icon={<MapPin className="h-4 w-4" />}
                title="Map"
                actions={
                    <>
                        <label className="flex items-center gap-2 text-xs text-muted-foreground mr-2">
                            <Switch
                                checked={showInactive}
                                onCheckedChange={setShowInactive}
                                aria-label="Show inactive locations"
                            />
                            Show inactive
                        </label>
                        <Button
                            size="sm"
                            variant={mode === 'add-location' ? 'default' : 'outline'}
                            onClick={() => switchMode('add-location')}
                        >
                            {mode === 'add-location' ? (
                                <X className="h-4 w-4" />
                            ) : (
                                <MapPin className="h-4 w-4" />
                            )}
                            Add location
                        </Button>
                        <Button
                            size="sm"
                            variant={mode === 'add-edge' ? 'default' : 'outline'}
                            onClick={() => switchMode('add-edge')}
                        >
                            {mode === 'add-edge' ? (
                                <X className="h-4 w-4" />
                            ) : (
                                <Spline className="h-4 w-4" />
                            )}
                            Add travel time
                        </Button>
                    </>
                }
            >
                {activeUnreachable.length > 0 && (
                    <div className="mb-4 flex items-start gap-2 rounded-lg border border-warning/30 bg-warning/10 px-4 py-3 text-sm text-warning-text">
                        <TriangleAlert className="h-4 w-4 mt-0.5 shrink-0" />
                        <span>
                            No route to the destination for:{' '}
                            <span className="font-medium">
                                {activeUnreachable.map((loc) => loc.name).join(', ')}
                            </span>
                            . Ride grouping will fail for these stops — connect them with a
                            travel time or set their from/to destination minutes.
                        </span>
                    </div>
                )}

                {MODE_HINTS[mode] && (
                    <div className="mb-4 rounded-lg border border-info/30 bg-info/10 px-4 py-2.5 text-sm text-info-text">
                        {MODE_HINTS[mode]}
                        {mode === 'add-edge' && pendingEdgeStartId != null && (
                            <span className="font-medium">
                                {' '}
                                First stop: {locationsById.get(pendingEdgeStartId)?.name}.
                            </span>
                        )}
                    </div>
                )}

                <LocationsMap
                    theme={theme}
                    locations={locations}
                    edges={edges}
                    unreachable={unreachable}
                    showInactive={showInactive}
                    mode={mode}
                    pendingEdgeStartId={pendingEdgeStartId}
                    flyTarget={flyTarget}
                    onMapClick={handleMapClick}
                    onMarkerClick={handleMarkerClick}
                    onEdgeClick={handleEdgeClick}
                    onEditLocation={(loc) => setLocationForm({ location: loc })}
                    onToggleActive={handleToggleActive}
                    onDeleteLocation={setDeleteTarget}
                />
            </SectionCard>

            <LocationsTable
                locations={locations}
                unreachable={unreachable}
                onRowClick={(loc) => setFlyTarget([loc.latitude, loc.longitude])}
                onEdit={(loc) => setLocationForm({ location: loc })}
                onToggleActive={handleToggleActive}
                onDelete={setDeleteTarget}
                onAdd={() => setLocationForm({ location: null })}
            />

            <TravelTimesSection
                locations={locations}
                edges={edges}
                submitting={manager.upsertEdge.isPending || manager.deleteEdge.isPending}
                onUpsert={(input) => manager.upsertEdge.mutate(input)}
                onDelete={(edgeId) => manager.deleteEdge.mutate(edgeId)}
            />

            <SettingsSection
                pickupAdjustment={data.pickup_adjustment}
                livingMappings={data.living_mappings}
                locations={locations}
                savingAdjustment={manager.savePickupAdjustment.isPending}
                savingMapping={manager.setLivingMapping.isPending}
                onSaveAdjustment={(value) => manager.savePickupAdjustment.mutate(value)}
                onSetMapping={(living_location, pickup_location_id) =>
                    manager.setLivingMapping.mutate({ living_location, pickup_location_id })
                }
            />

            <LocationFormDialog
                state={locationForm}
                submitting={manager.createLocation.isPending || manager.updateLocation.isPending}
                onSubmit={handleLocationSubmit}
                onClose={() => setLocationForm(null)}
            />

            <EdgeDialog
                state={edgeDialog}
                submitting={manager.upsertEdge.isPending || manager.deleteEdge.isPending}
                onSave={handleEdgeSave}
                onDelete={handleEdgeDelete}
                onClose={() => setEdgeDialog(null)}
            />

            <ConfirmDialog
                isOpen={deleteTarget != null}
                title="Delete location"
                description={
                    deleteTarget
                        ? `Delete "${deleteTarget.name}"? It will be removed from pickers, maps and routing. If a living location still points at it, you'll be asked to remap it first.`
                        : ''
                }
                confirmText="Delete"
                confirmVariant="destructive"
                onConfirm={() => {
                    if (deleteTarget) {
                        manager.deleteLocation.mutate(deleteTarget.id)
                    }
                    setDeleteTarget(null)
                }}
                onCancel={() => setDeleteTarget(null)}
            />
        </div>
    )
}

export default LocationManager
