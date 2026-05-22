import { useEffect, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiFetch } from '../lib/api'
import ErrorMessage from './ErrorMessage'
import { Button } from './ui/button'
import { Input } from './ui/input'
import ConfirmDialog from './ConfirmDialog'
import { TableSkeleton } from './LoadingSkeleton'
import { Car } from 'lucide-react'
import { SectionCard } from './shared'

interface Driver {
    discord_user_id: string
    discord_username: string
    display_name: string
}

interface SearchMember {
    discord_user_id: string
    discord_username: string
    display_name: string
}

interface DriverManagementProps {
    canManage: boolean
}

function DriverManagement({ canManage }: DriverManagementProps) {
    const queryClient = useQueryClient()
    const [searchInput, setSearchInput] = useState('')
    const [debouncedSearch, setDebouncedSearch] = useState('')
    const [showDropdown, setShowDropdown] = useState(false)
    const [removeTarget, setRemoveTarget] = useState<Driver | null>(null)
    const dropdownRef = useRef<HTMLDivElement>(null)

    useEffect(() => {
        const timer = setTimeout(() => setDebouncedSearch(searchInput), 300)
        return () => clearTimeout(timer)
    }, [searchInput])

    useEffect(() => {
        const handler = (e: MouseEvent) => {
            if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
                setShowDropdown(false)
            }
        }
        document.addEventListener('mousedown', handler)
        return () => document.removeEventListener('mousedown', handler)
    }, [])

    const { data, isLoading, error } = useQuery<{ drivers: Driver[] }>({
        queryKey: ['drivers'],
        queryFn: async () => {
            const res = await apiFetch('/api/drivers')
            return res.json()
        },
    })

    const { data: searchData } = useQuery<{ members: SearchMember[] }>({
        queryKey: ['driverSearch', debouncedSearch],
        queryFn: async () => {
            const res = await apiFetch(
                `/api/drivers/search?q=${encodeURIComponent(debouncedSearch)}`
            )
            return res.json()
        },
        enabled: canManage && debouncedSearch.length >= 2,
    })

    const addMutation = useMutation({
        mutationFn: async (username: string) => {
            const res = await apiFetch('/api/drivers', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ discord_username: username }),
            })
            return res.json()
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['drivers'] })
            setSearchInput('')
            setDebouncedSearch('')
            setShowDropdown(false)
        },
    })

    const removeMutation = useMutation({
        mutationFn: async (discordUserId: string) => {
            const res = await apiFetch(`/api/drivers/${encodeURIComponent(discordUserId)}`, {
                method: 'DELETE',
            })
            return res.json()
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['drivers'] })
        },
    })

    const handleRemoveConfirm = () => {
        if (removeTarget) removeMutation.mutate(removeTarget.discord_user_id)
        setRemoveTarget(null)
    }

    const handleSelectMember = (member: SearchMember) => {
        setSearchInput(member.discord_username)
        setDebouncedSearch(member.discord_username)
        setShowDropdown(false)
    }

    const drivers = data?.drivers ?? []
    const searchResults = searchData?.members ?? []
    const errorMsg = error instanceof Error ? error.message : ''

    return (
        <SectionCard icon={<Car className="h-4 w-4" />} title="Drivers">
            {isLoading && <TableSkeleton rows={3} cols={2} />}

            <div className="mb-6">
                <ErrorMessage message={errorMsg} />
            </div>

            {(addMutation.isError || removeMutation.isError) && (
                <div className="mb-4 px-3 py-2 rounded-md bg-destructive/15 border border-destructive/30 text-destructive-text text-sm">
                    ❌{' '}
                    {[addMutation.error, removeMutation.error].find(Boolean) instanceof Error
                        ? (
                              [addMutation.error, removeMutation.error].find(
                                  Boolean
                              ) as Error
                          ).message
                        : 'Operation failed'}
                </div>
            )}

            {canManage && (
                <div className="mb-6 p-4 rounded-lg border border-border bg-muted/30">
                    <p className="text-sm font-medium text-foreground mb-3">
                        Add driver by Discord username
                    </p>
                    <div className="flex flex-col sm:flex-row gap-2">
                        <div className="relative flex-1" ref={dropdownRef}>
                            <Input
                                type="text"
                                placeholder="Discord username (e.g. johndoe)"
                                autoComplete="off"
                                data-bwignore="true"
                                data-1p-ignore
                                value={searchInput}
                                onChange={(e) => {
                                    setSearchInput(e.target.value)
                                    setShowDropdown(true)
                                }}
                                onFocus={() => {
                                    if (searchInput.length >= 2) setShowDropdown(true)
                                }}
                            />
                            {showDropdown && searchResults.length > 0 && (
                                <div className="absolute z-10 w-full mt-1 bg-popover border border-border rounded-md shadow-md max-h-48 overflow-y-auto">
                                    {searchResults.map((member) => (
                                        <button
                                            key={member.discord_user_id}
                                            type="button"
                                            className="w-full text-left px-3 py-2 text-sm hover:bg-muted/50 transition-colors"
                                            onMouseDown={(e) => e.preventDefault()}
                                            onClick={() => handleSelectMember(member)}
                                        >
                                            <span className="font-medium text-foreground">
                                                @{member.discord_username}
                                            </span>
                                            {member.display_name !== member.discord_username && (
                                                <span className="ml-2 text-muted-foreground">
                                                    {member.display_name}
                                                </span>
                                            )}
                                        </button>
                                    ))}
                                </div>
                            )}
                        </div>
                        <Button
                            onClick={() => {
                                const username = searchInput.trim()
                                if (username) addMutation.mutate(username)
                            }}
                            disabled={!searchInput.trim() || addMutation.isPending}
                        >
                            {addMutation.isPending ? 'Adding…' : 'Add Driver'}
                        </Button>
                    </div>
                </div>
            )}

            {!isLoading && !errorMsg && drivers.length > 0 && (
                <div className="rounded-lg border border-border overflow-x-auto w-full max-w-[calc(100vw-3rem)]">
                    <table className="w-full text-left text-sm">
                        <thead className="bg-muted/50 text-foreground font-semibold border-b border-border">
                            <tr>
                                <th scope="col" className="px-3 sm:px-6 py-3 sm:py-4">
                                    Username
                                </th>
                                <th scope="col" className="px-3 sm:px-6 py-3 sm:py-4">
                                    Display Name
                                </th>
                                {canManage && (
                                    <th scope="col" className="px-3 sm:px-6 py-3 sm:py-4 w-12" />
                                )}
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-border">
                            {drivers.map((driver) => (
                                <tr
                                    key={driver.discord_user_id}
                                    className="hover:bg-muted/30 transition-colors"
                                >
                                    <td className="px-3 sm:px-6 py-3 sm:py-4">
                                        <span className="text-foreground font-medium">
                                            @{driver.discord_username}
                                        </span>
                                    </td>
                                    <td className="px-3 sm:px-6 py-3 sm:py-4 text-muted-foreground">
                                        {driver.display_name}
                                    </td>
                                    {canManage && (
                                        <td className="px-3 sm:px-6 py-3 sm:py-4">
                                            <Button
                                                variant="ghost"
                                                size="icon-sm"
                                                onClick={() => setRemoveTarget(driver)}
                                                disabled={removeMutation.isPending}
                                                className="text-muted-foreground hover:text-destructive hover:bg-destructive/10"
                                                title="Remove driver role"
                                            >
                                                ✕
                                            </Button>
                                        </td>
                                    )}
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}

            {!isLoading && !errorMsg && drivers.length === 0 && (
                <p className="text-muted-foreground italic p-4 text-center bg-muted/30 rounded-lg">
                    No drivers found.
                </p>
            )}

            <ConfirmDialog
                isOpen={removeTarget !== null}
                title="Remove driver role?"
                description={`Remove the Driver role from @${removeTarget?.discord_username ?? ''}? They will no longer be listed as a driver.`}
                confirmText="Remove"
                confirmVariant="destructive"
                onConfirm={handleRemoveConfirm}
                onCancel={() => setRemoveTarget(null)}
            />
        </SectionCard>
    )
}

export default DriverManagement
