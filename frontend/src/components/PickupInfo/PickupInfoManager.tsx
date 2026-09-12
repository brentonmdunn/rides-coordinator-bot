/**
 * PickupInfoManager.tsx
 *
 * Composition root for the Pickup Info page — wires the table, the
 * add/edit dialog, and the confirm dialog for single and bulk delete.
 */

import { useState } from 'react'
import ErrorMessage from '../ErrorMessage'
import { Input } from '../ui/input'
import { usePickupInfo, formDialogError } from './usePickupInfo'
import { PickupInfoTable } from './PickupInfoTable'
import { PickupInfoFormDialog, type PickupInfoFormState } from './PickupInfoFormDialog'
import { ConfirmDialog } from '../ConfirmDialog'
import type { PickupInfoPerson, PickupInfoPersonInput } from '../../types'

type DeleteTarget =
    | { kind: 'single'; person: PickupInfoPerson }
    | { kind: 'bulk'; ids: number[] }
    | { kind: 'all'; ids: number[] }

/** Typed confirmation required before wiping the whole pickupInfo. */
const DELETE_ALL_PHRASE = 'DELETE'

function PickupInfoManager() {
    const pickupInfo = usePickupInfo()
    const { data, isLoading, error } = pickupInfo.query

    const [formState, setFormState] = useState<PickupInfoFormState | null>(null)
    const [deleteTarget, setDeleteTarget] = useState<DeleteTarget | null>(null)
    const [deleteAllConfirm, setDeleteAllConfirm] = useState('')

    const people = data?.people ?? []

    const submitting = pickupInfo.createPerson.isPending || pickupInfo.updatePerson.isPending
    const submitError =
        formDialogError(pickupInfo.createPerson.error) ?? formDialogError(pickupInfo.updatePerson.error)

    const handleSubmit = (input: PickupInfoPersonInput) => {
        if (formState?.person) {
            pickupInfo.updatePerson.mutate(
                { id: formState.person.id, changes: input },
                { onSuccess: () => setFormState(null) }
            )
        } else {
            pickupInfo.createPerson.mutate(input, { onSuccess: () => setFormState(null) })
        }
    }

    const closeDeleteDialog = () => {
        setDeleteTarget(null)
        setDeleteAllConfirm('')
    }

    const handleConfirmDelete = () => {
        if (!deleteTarget) return
        if (deleteTarget.kind === 'single') {
            pickupInfo.deletePerson.mutate(deleteTarget.person.id)
        } else if (deleteTarget.kind === 'bulk') {
            pickupInfo.bulkDeletePeople.mutate(deleteTarget.ids)
        } else {
            if (deleteAllConfirm !== DELETE_ALL_PHRASE) return
            pickupInfo.deleteAllPeople.mutate(deleteTarget.ids)
        }
        closeDeleteDialog()
    }

    if (error) {
        return (
            <ErrorMessage
                message={error instanceof Error ? error.message : 'Failed to load pickup info'}
            />
        )
    }

    const isDeleteAll = deleteTarget?.kind === 'all'

    const deleteDescription =
        deleteTarget?.kind === 'single'
            ? `Delete "${deleteTarget.person.name}" from Pickup Info? This can't be undone.`
            : deleteTarget?.kind === 'bulk'
              ? `Delete ${deleteTarget.ids.length} people from Pickup Info? This can't be undone.`
              : deleteTarget?.kind === 'all'
                ? `Delete all ${deleteTarget.ids.length} people from Pickup Info? This can't be undone. Everyone would have to add their pickup info again, and pickup grouping will be empty until they do.`
                : ''

    return (
        <div className="space-y-8">
            <PickupInfoTable
                people={people}
                options={pickupInfo.optionsQuery.data}
                isLoading={isLoading}
                onEdit={(person) => setFormState({ person })}
                onDelete={(person) => setDeleteTarget({ kind: 'single', person })}
                onBulkDelete={(ids) => setDeleteTarget({ kind: 'bulk', ids })}
                onDeleteAll={() =>
                    setDeleteTarget({ kind: 'all', ids: people.map((person) => person.id) })
                }
                onAdd={() => setFormState({ person: null })}
            />

            <PickupInfoFormDialog
                state={formState}
                options={pickupInfo.optionsQuery.data}
                submitting={submitting}
                error={submitError}
                onSubmit={handleSubmit}
                onClose={() => setFormState(null)}
            />

            <ConfirmDialog
                isOpen={deleteTarget != null}
                title={isDeleteAll ? 'Delete all pickup info' : 'Delete from Pickup Info'}
                description={deleteDescription}
                confirmText={isDeleteAll ? 'Delete everyone' : 'Delete'}
                confirmVariant="destructive"
                confirmDisabled={isDeleteAll && deleteAllConfirm !== DELETE_ALL_PHRASE}
                onConfirm={handleConfirmDelete}
                onCancel={closeDeleteDialog}
            >
                {isDeleteAll && (
                    <div className="space-y-1.5">
                        <label
                            htmlFor="pickup-info-delete-all-confirm"
                            className="text-sm font-medium text-foreground"
                        >
                            Type {DELETE_ALL_PHRASE} to confirm
                        </label>
                        <Input
                            id="pickup-info-delete-all-confirm"
                            value={deleteAllConfirm}
                            onChange={(e) => setDeleteAllConfirm(e.target.value)}
                            placeholder={DELETE_ALL_PHRASE}
                            autoComplete="off"
                        />
                    </div>
                )}
            </ConfirmDialog>
        </div>
    )
}

export default PickupInfoManager
