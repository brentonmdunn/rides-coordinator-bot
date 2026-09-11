/**
 * RosterManager.tsx
 *
 * Composition root for the Roster management page — wires the table, the
 * add/edit dialog, and the confirm dialog for single and bulk delete.
 */

import { useState } from 'react'
import ErrorMessage from '../ErrorMessage'
import { useRoster, formDialogError } from './useRoster'
import { RosterTable } from './RosterTable'
import { RosterFormDialog, type RosterFormState } from './RosterFormDialog'
import { ConfirmDialog } from '../ConfirmDialog'
import type { RosterPerson, RosterPersonInput } from '../../types'

type DeleteTarget = { kind: 'single'; person: RosterPerson } | { kind: 'bulk'; ids: number[] }

function RosterManager() {
    const roster = useRoster()
    const { data, isLoading, error } = roster.query

    const [formState, setFormState] = useState<RosterFormState | null>(null)
    const [deleteTarget, setDeleteTarget] = useState<DeleteTarget | null>(null)

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

    const handleConfirmDelete = () => {
        if (!deleteTarget) return
        if (deleteTarget.kind === 'single') {
            roster.deletePerson.mutate(deleteTarget.person.id)
        } else {
            roster.bulkDeletePeople.mutate(deleteTarget.ids)
        }
        setDeleteTarget(null)
    }

    if (error) {
        return (
            <ErrorMessage
                message={error instanceof Error ? error.message : 'Failed to load roster'}
            />
        )
    }

    const deleteDescription =
        deleteTarget?.kind === 'single'
            ? `Delete "${deleteTarget.person.name}" from the roster? This can't be undone.`
            : deleteTarget?.kind === 'bulk'
              ? `Delete ${deleteTarget.ids.length} people from the roster? This can't be undone.`
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
                title="Delete from roster"
                description={deleteDescription}
                confirmText="Delete"
                confirmVariant="destructive"
                onConfirm={handleConfirmDelete}
                onCancel={() => setDeleteTarget(null)}
            />
        </div>
    )
}

export default RosterManager
