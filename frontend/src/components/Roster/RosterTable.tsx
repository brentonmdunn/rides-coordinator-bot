/**
 * RosterTable.tsx
 *
 * Table of every roster person — searchable, sortable, multi-select with
 * bulk delete, and per-row edit/delete. Flags rows whose `year` doesn't
 * match a current option with a "Needs fix" badge; off-campus locations
 * are valid free text and are never flagged.
 * Scrolls horizontally at phone width instead of squeezing columns.
 */

import { useMemo, useState } from 'react'
import { ArrowDown, ArrowUp, ArrowUpDown, Pencil, Trash2, Users } from 'lucide-react'
import { Button } from '../ui/button'
import { Input } from '../ui/input'
import { Checkbox } from '../ui/checkbox'
import { SectionCard } from '../shared'
import { TableSkeleton } from '../LoadingSkeleton'
import type { RosterOptions, RosterPerson } from '../../types'

interface RosterTableProps {
    people: RosterPerson[]
    options: RosterOptions | undefined
    isLoading: boolean
    onEdit: (person: RosterPerson) => void
    onDelete: (person: RosterPerson) => void
    onBulkDelete: (ids: number[]) => void
    onDeleteAll: () => void
    onAdd: () => void
}

type SortKey = 'name' | 'discord_username' | 'year' | 'location' | 'linked' | 'updated_at'
type SortDir = 'asc' | 'desc'

const COLUMNS: { key: SortKey; label: string }[] = [
    { key: 'name', label: 'Name' },
    { key: 'discord_username', label: 'Discord username' },
    { key: 'year', label: 'Year' },
    { key: 'location', label: 'Location' },
    { key: 'linked', label: 'Linked' },
    { key: 'updated_at', label: 'Updated' },
]

function formatRelativeTime(iso: string | null): string {
    if (!iso) return '—'
    const date = new Date(iso)
    if (Number.isNaN(date.getTime())) return '—'

    const diffMs = Date.now() - date.getTime()
    const diffSec = Math.round(diffMs / 1000)
    const diffMin = Math.round(diffSec / 60)
    const diffHour = Math.round(diffMin / 60)
    const diffDay = Math.round(diffHour / 24)

    if (diffSec < 60) return 'just now'
    if (diffMin < 60) return `${diffMin}m ago`
    if (diffHour < 24) return `${diffHour}h ago`
    if (diffDay < 30) return `${diffDay}d ago`
    return date.toLocaleDateString()
}

function needsFix(person: RosterPerson, options: RosterOptions | undefined): boolean {
    if (!options) return false
    // Locations outside the campus list are valid off-campus addresses, not errors.
    return person.year != null && !options.years.includes(person.year)
}

function compareValues(a: RosterPerson, b: RosterPerson, key: SortKey): number {
    if (key === 'linked') {
        return Number(a.discord_user_id != null) - Number(b.discord_user_id != null)
    }
    if (key === 'updated_at') {
        const aTime = a.updated_at ? new Date(a.updated_at).getTime() : 0
        const bTime = b.updated_at ? new Date(b.updated_at).getTime() : 0
        return aTime - bTime
    }
    const aValue = (a[key] ?? '').toString().toLowerCase()
    const bValue = (b[key] ?? '').toString().toLowerCase()
    return aValue.localeCompare(bValue)
}

export function RosterTable({
    people,
    options,
    isLoading,
    onEdit,
    onDelete,
    onBulkDelete,
    onDeleteAll,
    onAdd,
}: RosterTableProps) {
    const [search, setSearch] = useState('')
    const [sortKey, setSortKey] = useState<SortKey>('name')
    const [sortDir, setSortDir] = useState<SortDir>('asc')
    const [selected, setSelected] = useState<Set<number>>(new Set())

    const filtered = useMemo(() => {
        const term = search.trim().toLowerCase()
        const rows = term
            ? people.filter(
                  (person) =>
                      person.name.toLowerCase().includes(term) ||
                      (person.discord_username ?? '').toLowerCase().includes(term)
              )
            : people

        const sorted = [...rows].sort((a, b) => {
            const cmp = compareValues(a, b, sortKey)
            return sortDir === 'asc' ? cmp : -cmp
        })
        return sorted
    }, [people, search, sortKey, sortDir])

    const filteredIds = useMemo(() => new Set(filtered.map((p) => p.id)), [filtered])
    const selectedInView = useMemo(
        () => [...selected].filter((id) => filteredIds.has(id)),
        [selected, filteredIds]
    )
    const allSelected = filtered.length > 0 && selectedInView.length === filtered.length

    const toggleSort = (key: SortKey) => {
        if (key === sortKey) {
            setSortDir((dir) => (dir === 'asc' ? 'desc' : 'asc'))
        } else {
            setSortKey(key)
            setSortDir('asc')
        }
    }

    const toggleSelectAll = () => {
        setSelected((prev) => {
            const next = new Set(prev)
            if (allSelected) {
                filtered.forEach((p) => next.delete(p.id))
            } else {
                filtered.forEach((p) => next.add(p.id))
            }
            return next
        })
    }

    const toggleSelectRow = (id: number) => {
        setSelected((prev) => {
            const next = new Set(prev)
            if (next.has(id)) {
                next.delete(id)
            } else {
                next.add(id)
            }
            return next
        })
    }

    const handleBulkDelete = () => {
        onBulkDelete(selectedInView)
        setSelected(new Set())
    }

    if (isLoading) {
        return (
            <SectionCard icon={<Users className="h-4 w-4" />} title="Roster">
                <TableSkeleton rows={6} cols={6} />
            </SectionCard>
        )
    }

    return (
        <SectionCard
            icon={<Users className="h-4 w-4" />}
            title="Roster"
            actions={
                <div className="flex items-center gap-2">
                    {people.length > 0 && (
                        <Button size="sm" variant="destructive" onClick={onDeleteAll}>
                            <Trash2 className="h-4 w-4" />
                            Delete all
                        </Button>
                    )}
                    <Button size="sm" onClick={onAdd}>
                        Add person
                    </Button>
                </div>
            }
        >
            <div className="flex flex-col sm:flex-row sm:items-center gap-2 mb-3">
                <Input
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    placeholder="Search by name or username…"
                    className="sm:max-w-xs"
                    aria-label="Search roster"
                />
                {selectedInView.length > 0 && (
                    <Button
                        size="sm"
                        variant="destructive"
                        onClick={handleBulkDelete}
                        className="sm:ml-auto"
                    >
                        <Trash2 className="h-4 w-4" />
                        Delete selected ({selectedInView.length})
                    </Button>
                )}
            </div>

            {filtered.length === 0 ? (
                <p className="text-sm text-muted-foreground py-4 text-center">
                    {people.length === 0
                        ? 'No one on the roster yet.'
                        : 'No matches for your search.'}
                </p>
            ) : (
                <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                        <thead>
                            <tr className="border-b border-border text-left text-xs uppercase tracking-wide text-muted-foreground">
                                <th className="px-3 py-2 font-medium">
                                    <Checkbox
                                        checked={allSelected}
                                        onCheckedChange={toggleSelectAll}
                                        aria-label="Select all"
                                    />
                                </th>
                                {COLUMNS.map((column) => (
                                    <th key={column.key} className="px-3 py-2 font-medium">
                                        <button
                                            type="button"
                                            onClick={() => toggleSort(column.key)}
                                            className="inline-flex items-center gap-1 hover:text-foreground transition-colors"
                                        >
                                            {column.label}
                                            {sortKey === column.key ? (
                                                sortDir === 'asc' ? (
                                                    <ArrowUp className="h-3 w-3" />
                                                ) : (
                                                    <ArrowDown className="h-3 w-3" />
                                                )
                                            ) : (
                                                <ArrowUpDown className="h-3 w-3 opacity-40" />
                                            )}
                                        </button>
                                    </th>
                                ))}
                                <th className="px-3 py-2 font-medium">Actions</th>
                            </tr>
                        </thead>
                        <tbody>
                            {filtered.map((person) => (
                                <tr
                                    key={person.id}
                                    className="border-b border-border last:border-0 hover:bg-muted/50"
                                >
                                    <td className="px-3 py-2">
                                        <Checkbox
                                            checked={selected.has(person.id)}
                                            onCheckedChange={() => toggleSelectRow(person.id)}
                                            aria-label={`Select ${person.name}`}
                                        />
                                    </td>
                                    <td className="px-3 py-2">
                                        <div className="flex items-center gap-1.5 font-medium text-foreground">
                                            {person.name}
                                            {needsFix(person, options) && (
                                                <span className="inline-flex items-center rounded-full border border-warning/30 bg-warning/10 px-1.5 py-0.5 text-xs font-medium text-warning-text">
                                                    Needs fix
                                                </span>
                                            )}
                                        </div>
                                    </td>
                                    <td className="px-3 py-2 text-muted-foreground whitespace-nowrap">
                                        {person.discord_username ?? '—'}
                                    </td>
                                    <td className="px-3 py-2 text-muted-foreground whitespace-nowrap">
                                        {person.year ?? '—'}
                                    </td>
                                    <td className="px-3 py-2 text-muted-foreground whitespace-nowrap">
                                        {person.location ?? '—'}
                                    </td>
                                    <td className="px-3 py-2 whitespace-nowrap">
                                        {person.discord_user_id != null ? (
                                            <span className="inline-flex items-center rounded-full border border-success/30 bg-success/10 px-1.5 py-0.5 text-xs font-medium text-success-text">
                                                Linked
                                            </span>
                                        ) : (
                                            <span className="inline-flex items-center rounded-full border border-border bg-muted px-1.5 py-0.5 text-xs font-medium text-muted-foreground">
                                                Not linked
                                            </span>
                                        )}
                                    </td>
                                    <td className="px-3 py-2 text-muted-foreground whitespace-nowrap">
                                        {formatRelativeTime(person.updated_at)}
                                    </td>
                                    <td className="px-3 py-2">
                                        <div className="flex items-center gap-1">
                                            <Button
                                                variant="ghost"
                                                size="icon"
                                                onClick={() => onEdit(person)}
                                                title="Edit"
                                            >
                                                <Pencil className="h-4 w-4" />
                                            </Button>
                                            <Button
                                                variant="ghost"
                                                size="icon"
                                                onClick={() => onDelete(person)}
                                                title="Delete"
                                                className="text-destructive-text hover:text-destructive-text"
                                            >
                                                <Trash2 className="h-4 w-4" />
                                            </Button>
                                        </div>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}
        </SectionCard>
    )
}

export default RosterTable
