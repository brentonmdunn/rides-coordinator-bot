/**
 * RosterManager.tsx
 *
 * Composition root for the Roster management page — wires the table, the
 * add/edit dialog, and the confirm dialog for single and bulk delete.
 */

import { useState } from 'react'
import ErrorMessage from '../ErrorMessage'
import { Input } from '../ui/input'
import { useRoster, formDialogError } from './useRoster'
import { RosterTable } from './RosterTable'
import { RosterFormDialog, type RosterFormState } from './RosterFormDialog'
import { ConfirmDialog } from '../ConfirmDialog'
import type { RosterPerson, RosterPersonInput } from '../../types'

type DeleteTarget =
    | { kind: 'single'; person: RosterPerson }
    | { kind: 'bulk'; ids: number[] }
    | { kind: 'all'; ids: number[] }

/** Typed confirmation required before wiping the whole roster. */
const DELETE_ALL_PHRASE = 'DELETE'

function RosterManager() {
    const roster = useRoster()
    const { data, isLoading, error } = roster.query

    const [formState, setFormState] = useState<RosterFormState | null>(null)
    const [deleteTarget, setDeleteTarget] = useState<DeleteTarget | null>(null)
    const [deleteAllConfirm, setDeleteAllConfirm] = useState('')

    const people = data?.people ?? []

    const submitting = roster.createPerson.isPending || roster.updatePerson.isPending
    const submitError =
        formDialogError(roster.createPerson.error) ?? formDialogError(roster.updatePerson.error)

    const handleSubmit = (input: RosterPersonInput) => {
        if (formState?.person) {
            roster.updatePerson.mutate(
                { id: formState.person.id, changes: input },
                { onSuccess: () => setFormState(null) }
            )
        } else {
            roster.createPerson.mutate(input, { onSuccess: () => setFormState(null) })
        }
    }

    const closeDeleteDialog = () => {
        setDeleteTarget(null)
        setDeleteAllConfirm('')
    }

    const handleConfirmDelete = () => {
        if (!deleteTarget) return
        if (deleteTarget.kind === 'single') {
            roster.deletePerson.mutate(deleteTarget.person.id)
        } else if (deleteTarget.kind === 'bulk') {
            roster.bulkDeletePeople.mutate(deleteTarget.ids)
        } else {
            if (deleteAllConfirm !== DELETE_ALL_PHRASE) return
            roster.deleteAllPeople.mutate(deleteTarget.ids)
        }
        closeDeleteDialog()
    }

    if (error) {
        return (
            <ErrorMessage
                message={error instanceof Error ? error.message : 'Failed to load roster'}
            />
        )
    }

    const isDeleteAll = deleteTarget?.kind === 'all'

    const deleteDescription =
        deleteTarget?.kind === 'single'
            ? `Delete "${deleteTarget.person.name}" from the roster? This can't be undone.`
            : deleteTarget?.kind === 'bulk'
              ? `Delete ${deleteTarget.ids.length} people from the roster? This can't be undone.`
              : deleteTarget?.kind === 'all'
                ? `Delete all ${deleteTarget.ids.length} people from the roster? This can't be undone. Everyone would have to add their pickup info again, and pickup grouping will be empty until they do.`
                : ''

    return (
        <div className="space-y-8">
            <RosterTable
                people={people}
                options={roster.optionsQuery.data}
                isLoading={isLoading}
                onEdit={(person) => setFormState({ person })}
                onDelete={(person) => setDeleteTarget({ kind: 'single', person })}
                onBulkDelete={(ids) => setDeleteTarget({ kind: 'bulk', ids })}
                onDeleteAll={() =>
                    setDeleteTarget({ kind: 'all', ids: people.map((person) => person.id) })
                }
                onAdd={() => setFormState({ person: null })}
            />

            <RosterFormDialog
                state={formState}
                options={roster.optionsQuery.data}
                submitting={submitting}
                error={submitError}
                onSubmit={handleSubmit}
                onClose={() => setFormState(null)}
            />

            <ConfirmDialog
                isOpen={deleteTarget != null}
                title={isDeleteAll ? 'Delete the entire roster' : 'Delete from roster'}
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
                            htmlFor="roster-delete-all-confirm"
                            className="text-sm font-medium text-foreground"
                        >
                            Type {DELETE_ALL_PHRASE} to confirm
                        </label>
                        <Input
                            id="roster-delete-all-confirm"
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

export default RosterManager
