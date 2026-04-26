/**
 * LocationCombobox.tsx
 *
 * Multi-select combobox for picking pickup locations. Replaces the older
 * dropdown + "Add Location" button flow: clicking a row toggles add/remove,
 * the popover stays open for rapid multi-pick, and a search input filters
 * the list.
 */

import { useEffect, useMemo, useRef, useState } from 'react'
import { Check, ChevronDown, Plus, Search } from 'lucide-react'
import { Popover } from 'radix-ui'
import type { PickupLocationsResponse } from '../../types'

export interface LocationComboboxProps {
    locations: PickupLocationsResponse | undefined
    loading: boolean
    selectedKeys: string[]
    onToggle: (key: string) => void
}

export function LocationCombobox({
    locations,
    loading,
    selectedKeys,
    onToggle,
}: LocationComboboxProps) {
    const [open, setOpen] = useState(false)
    const [query, setQuery] = useState('')
    const inputRef = useRef<HTMLInputElement>(null)

    useEffect(() => {
        if (!open) return
        // Defer focus so it lands after the popover has mounted
        const id = window.setTimeout(() => inputRef.current?.focus(), 30)
        return () => window.clearTimeout(id)
    }, [open])

    const handleOpenChange = (next: boolean) => {
        setOpen(next)
        if (!next) setQuery('')
    }

    const filtered = useMemo(() => {
        const items = locations?.locations ?? []
        const q = query.trim().toLowerCase()
        if (!q) return items
        return items.filter((loc) => loc.value.toLowerCase().includes(q))
    }, [locations, query])

    const selectedCount = selectedKeys.length
    const triggerLabel = loading
        ? 'Loading locations…'
        : selectedCount === 0
            ? 'Select pickup locations'
            : `${selectedCount} location${selectedCount === 1 ? '' : 's'} selected`

    return (
        <Popover.Root open={open} onOpenChange={handleOpenChange}>
            <Popover.Trigger asChild>
                <button
                    type="button"
                    disabled={loading}
                    aria-haspopup="listbox"
                    aria-expanded={open}
                    className="flex h-9 w-full items-center justify-between gap-2 rounded-md border border-input bg-transparent px-3 text-sm whitespace-nowrap shadow-xs transition-colors outline-none focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50 disabled:cursor-not-allowed disabled:opacity-50 dark:bg-input/30 dark:hover:bg-input/50"
                >
                    <span
                        className={
                            selectedCount === 0
                                ? 'text-muted-foreground'
                                : 'text-slate-900 dark:text-slate-100'
                        }
                    >
                        {triggerLabel}
                    </span>
                    <ChevronDown className="h-4 w-4 shrink-0 opacity-50" />
                </button>
            </Popover.Trigger>
            <Popover.Portal>
                <Popover.Content
                    align="start"
                    sideOffset={4}
                    className="z-[1100] w-[var(--radix-popover-trigger-width)] min-w-[16rem] rounded-md border border-slate-200 dark:border-zinc-700 bg-white dark:bg-zinc-900 shadow-lg outline-none"
                >
                    <div className="flex items-center gap-2 border-b border-slate-200 dark:border-zinc-700 px-3 py-2">
                        <Search className="h-4 w-4 text-slate-400 shrink-0" />
                        <input
                            ref={inputRef}
                            value={query}
                            onChange={(e) => setQuery(e.target.value)}
                            placeholder="Search locations…"
                            className="flex-1 bg-transparent text-sm text-slate-900 dark:text-slate-100 placeholder:text-slate-400 outline-none"
                        />
                    </div>
                    <div
                        role="listbox"
                        aria-multiselectable="true"
                        className="max-h-64 overflow-y-auto py-1"
                    >
                        {filtered.length === 0 ? (
                            <div className="px-3 py-6 text-center text-xs text-slate-500 dark:text-slate-400">
                                {locations && locations.locations.length === 0
                                    ? 'No locations available'
                                    : 'No matches'}
                            </div>
                        ) : (
                            filtered.map((loc) => {
                                const isSelected = selectedKeys.includes(loc.key)
                                return (
                                    <button
                                        key={loc.key}
                                        type="button"
                                        role="option"
                                        aria-selected={isSelected}
                                        onClick={() => onToggle(loc.key)}
                                        className={`flex w-full items-center gap-2 px-3 py-2 text-left text-sm transition-colors ${isSelected
                                            ? 'bg-emerald-50 dark:bg-emerald-900/20 text-emerald-700 dark:text-emerald-300'
                                            : 'text-slate-700 dark:text-slate-200 hover:bg-slate-100 dark:hover:bg-zinc-800'
                                            }`}
                                    >
                                        <span className="flex h-4 w-4 shrink-0 items-center justify-center">
                                            {isSelected ? (
                                                <Check className="h-4 w-4" />
                                            ) : (
                                                <Plus className="h-3.5 w-3.5 text-slate-400" />
                                            )}
                                        </span>
                                        <span className="flex-1 truncate">{loc.value}</span>
                                    </button>
                                )
                            })
                        )}
                    </div>
                </Popover.Content>
            </Popover.Portal>
        </Popover.Root>
    )
}
