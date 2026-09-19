import { Fragment, useEffect, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { apiFetch, ApiError } from '../lib/api'
import ErrorMessage from './ErrorMessage'
import { Button } from './ui/button'
import { Input } from './ui/input'
import { TableSkeleton } from './LoadingSkeleton'
import { SegmentedControl } from './ui/segmented-control'
import { UserCheck } from 'lucide-react'
import { SectionCard } from './shared'
import {
    DEFAULT_DURATION_PRESET,
    DURATION_PRESETS,
    formatExpiryBadge,
    formatFullDateTime,
    getDateInputBounds,
    resolveHelperText,
} from '../lib/tempDriver'

interface Member {
    discord_user_id: string
    discord_username: string
    display_name: string
    temp_expires_at?: string | null
}

interface RoleConfig {
    label: string
    apiPath: string
    queryKey: string
    /** Only true for the Drivers tab — enables the Permanent/Temporary add flow. */
    supportsTemporary?: boolean
}

type AddMode = 'permanent' | 'temporary'

const ADD_MODE_OPTIONS: { value: AddMode; label: string }[] = [
    { value: 'permanent', label: 'Permanent' },
    { value: 'temporary', label: 'Temporary' },
]

function errorMessage(error: unknown): string {
    if (error instanceof ApiError) return error.detail
    if (error instanceof Error) return error.message
    return 'Request failed'
}

/**
 * Preset chips + custom date input shared by the add control and the
 * "change expiry" row action. Reports the current `duration` value
 * ("3d" | "1w" | "2w" | "30d" | "YYYY-MM-DD") to the parent.
 */
function DurationPicker({
    duration,
    onChange,
    disabled,
}: {
    duration: string
    onChange: (value: string) => void
    disabled?: boolean
}) {
    const { min, max } = getDateInputBounds()
    const helperText = resolveHelperText(duration)

    return (
        <div className="flex flex-col gap-2">
            <div className="flex flex-wrap gap-1.5">
                {DURATION_PRESETS.map((preset) => (
                    <Button
                        key={preset.value}
                        type="button"
                        variant={duration === preset.value ? 'default' : 'outline'}
                        size="sm"
                        className="h-7 text-xs px-2.5"
                        disabled={disabled}
                        onClick={() => onChange(preset.value)}
                    >
                        {preset.label}
                    </Button>
                ))}
                <Input
                    type="date"
                    aria-label="Custom expiry date"
                    min={min}
                    max={max}
                    disabled={disabled}
                    value={/^\d{4}-\d{2}-\d{2}$/.test(duration) ? duration : ''}
                    onChange={(e) => {
                        if (e.target.value) onChange(e.target.value)
                    }}
                    className="h-7 w-auto text-xs px-2"
                />
            </div>
            {helperText && <p className="text-xs text-muted-foreground">{helperText}</p>}
        </div>
    )
}

type TabValue = 'drivers' | 'ride-coordinators'

const TABS: { value: TabValue; label: string }[] = [
    { value: 'drivers', label: 'Drivers' },
    { value: 'ride-coordinators', label: 'Ride Coordinators' },
]

const ROLE_CONFIGS: Record<TabValue, RoleConfig> = {
    drivers: {
        label: 'Driver',
        apiPath: '/api/drivers',
        queryKey: 'drivers',
        supportsTemporary: true,
    },
    'ride-coordinators': {
        label: 'Ride Coordinator',
        apiPath: '/api/ride-coordinators',
        queryKey: 'ride-coordinators',
    },
}

function RolePanel({ config, canManage }: { config: RoleConfig; canManage: boolean }) {
    const queryClient = useQueryClient()
    const [searchInput, setSearchInput] = useState('')
    const [debouncedSearch, setDebouncedSearch] = useState('')
    const [showDropdown, setShowDropdown] = useState(false)
    const [highlightedIndex, setHighlightedIndex] = useState(-1)
    const [confirmRemoveId, setConfirmRemoveId] = useState<string | null>(null)
    const [addMode, setAddMode] = useState<AddMode>('permanent')
    const [tempDuration, setTempDuration] = useState(DEFAULT_DURATION_PRESET)
    const [editingExpiryId, setEditingExpiryId] = useState<string | null>(null)
    const [editDuration, setEditDuration] = useState(DEFAULT_DURATION_PRESET)
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

    const { data, isLoading, error } = useQuery<{ members: Member[] }>({
        queryKey: [config.queryKey],
        queryFn: async () => {
            const res = await apiFetch(config.apiPath)
            return res.json()
        },
    })

    const { data: searchData } = useQuery<{ members: Member[] }>({
        queryKey: [`${config.queryKey}Search`, debouncedSearch],
        queryFn: async () => {
            const res = await apiFetch(
                `${config.apiPath}/search?q=${encodeURIComponent(debouncedSearch)}`
            )
            return res.json()
        },
        enabled: canManage && debouncedSearch.length >= 2,
    })

    const addMutation = useMutation({
        mutationFn: async (username: string) => {
            const res = await apiFetch(config.apiPath, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ discord_username: username }),
            })
            return res.json()
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: [config.queryKey] })
            setSearchInput('')
            setDebouncedSearch('')
            setShowDropdown(false)
        },
    })

    const removeMutation = useMutation({
        mutationFn: async (discordUserId: string) => {
            const res = await apiFetch(
                `${config.apiPath}/${encodeURIComponent(discordUserId)}`,
                { method: 'DELETE' }
            )
            return res.json()
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: [config.queryKey] })
            setConfirmRemoveId(null)
        },
    })

    const tempAddMutation = useMutation({
        mutationFn: async ({ username, duration }: { username: string; duration: string }) => {
            const res = await apiFetch('/api/drivers/temp', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ discord_username: username, duration }),
            })
            return res.json() as Promise<{ event: 'granted' | 'extended' }>
        },
        onSuccess: (result) => {
            queryClient.invalidateQueries({ queryKey: [config.queryKey] })
            setSearchInput('')
            setDebouncedSearch('')
            setShowDropdown(false)
            setTempDuration(DEFAULT_DURATION_PRESET)
            toast.success(
                result.event === 'extended'
                    ? 'Temporary driver expiry updated'
                    : 'Temporary driver added'
            )
        },
        onError: (error) => toast.error(errorMessage(error)),
    })

    const changeExpiryMutation = useMutation({
        mutationFn: async ({ username, duration }: { username: string; duration: string }) => {
            const res = await apiFetch('/api/drivers/temp', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ discord_username: username, duration }),
            })
            return res.json()
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: [config.queryKey] })
            setEditingExpiryId(null)
            toast.success('Expiry updated')
        },
        onError: (error) => toast.error(errorMessage(error)),
    })

    const makePermanentMutation = useMutation({
        mutationFn: async (username: string) => {
            const res = await apiFetch(config.apiPath, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ discord_username: username }),
            })
            return res.json()
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: [config.queryKey] })
            toast.success('Now a permanent driver')
        },
        onError: (error) => toast.error(errorMessage(error)),
    })

    const handleSelectMember = (member: Member) => {
        setSearchInput(member.discord_username)
        setDebouncedSearch(member.discord_username)
        setShowDropdown(false)
        setHighlightedIndex(-1)
    }

    const members = data?.members ?? []
    const searchResults = searchData?.members ?? []

    const handleSearchKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
        if (!showDropdown || searchResults.length === 0) return
        if (e.key === 'ArrowDown') {
            e.preventDefault()
            setHighlightedIndex((i) => (i + 1) % searchResults.length)
        } else if (e.key === 'ArrowUp') {
            e.preventDefault()
            setHighlightedIndex((i) => (i <= 0 ? searchResults.length - 1 : i - 1))
        } else if (e.key === 'Enter' && highlightedIndex >= 0) {
            e.preventDefault()
            handleSelectMember(searchResults[highlightedIndex])
        } else if (e.key === 'Escape') {
            setShowDropdown(false)
            setHighlightedIndex(-1)
        }
    }

    const errorMsg = error instanceof Error ? error.message : ''
    const labelLower = config.label.toLowerCase()

    return (
        <>
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
                        Add {labelLower} by Discord username
                    </p>
                    {config.supportsTemporary && (
                        <div className="mb-3">
                            <SegmentedControl
                                options={ADD_MODE_OPTIONS}
                                value={addMode}
                                onChange={setAddMode}
                            />
                        </div>
                    )}
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
                                    setHighlightedIndex(-1)
                                }}
                                onFocus={() => {
                                    if (searchInput.length >= 2) setShowDropdown(true)
                                }}
                                onKeyDown={handleSearchKeyDown}
                            />
                            {showDropdown && searchResults.length > 0 && (
                                <div className="absolute z-10 w-full mt-1 bg-popover border border-border rounded-md shadow-md max-h-48 overflow-y-auto">
                                    {searchResults.map((member, index) => (
                                        <button
                                            key={member.discord_user_id}
                                            type="button"
                                            className={`w-full text-left px-3 py-2 text-sm transition-colors ${highlightedIndex === index ? 'bg-muted/70' : 'hover:bg-muted/50'}`}
                                            onMouseDown={(e) => e.preventDefault()}
                                            onMouseEnter={() => setHighlightedIndex(index)}
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
                                if (!username) return
                                if (config.supportsTemporary && addMode === 'temporary') {
                                    tempAddMutation.mutate({ username, duration: tempDuration })
                                } else {
                                    addMutation.mutate(username)
                                }
                            }}
                            disabled={
                                !searchInput.trim() ||
                                addMutation.isPending ||
                                tempAddMutation.isPending
                            }
                        >
                            {addMutation.isPending || tempAddMutation.isPending
                                ? 'Adding…'
                                : config.supportsTemporary && addMode === 'temporary'
                                  ? 'Add Temporary Driver'
                                  : `Add ${config.label}`}
                        </Button>
                    </div>
                    {config.supportsTemporary && addMode === 'temporary' && (
                        <div className="mt-3">
                            <DurationPicker duration={tempDuration} onChange={setTempDuration} />
                        </div>
                    )}
                </div>
            )}

            {!isLoading && !errorMsg && members.length > 0 && (
                <div className="rounded-lg border border-border overflow-x-auto w-full max-w-[calc(100vw-3rem)]">
                    <table className="w-full table-fixed text-left text-sm">
                        <thead className="bg-muted/50 text-foreground font-semibold border-b border-border">
                            <tr>
                                <th scope="col" className="px-3 sm:px-6 py-3 sm:py-4 w-[45%]">
                                    Username
                                </th>
                                <th scope="col" className="px-3 sm:px-6 py-3 sm:py-4">
                                    Display Name
                                </th>
                                {canManage && (
                                    <th
                                        scope="col"
                                        className={`px-3 sm:px-6 py-3 sm:py-4 ${config.supportsTemporary ? 'w-56' : 'w-36'}`}
                                    />
                                )}
                            </tr>
                        </thead>
                        <tbody>
                            {members.map((member) => (
                                <Fragment key={member.discord_user_id}>
                                    <tr className="border-t border-border hover:bg-muted/30 transition-colors">
                                        <td className="px-3 sm:px-6 py-3 sm:py-4">
                                            <span className="text-foreground font-medium">
                                                @{member.discord_username}
                                            </span>
                                        </td>
                                        <td className="px-3 sm:px-6 py-3 sm:py-4 text-muted-foreground">
                                            <div className="flex flex-wrap items-center gap-2">
                                                <span>{member.display_name}</span>
                                                {member.temp_expires_at && (
                                                    <span
                                                        className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium bg-warning/10 text-warning-text border border-warning/30"
                                                        title={formatFullDateTime(
                                                            member.temp_expires_at
                                                        )}
                                                    >
                                                        {formatExpiryBadge(
                                                            member.temp_expires_at
                                                        )}
                                                    </span>
                                                )}
                                            </div>
                                        </td>
                                        {canManage && (
                                            <td
                                                className={`px-3 sm:px-6 ${config.supportsTemporary ? 'w-56' : 'w-36'}`}
                                            >
                                                {editingExpiryId === member.discord_user_id ? (
                                                    <div className="flex flex-col items-end gap-2 py-2">
                                                        <DurationPicker
                                                            duration={editDuration}
                                                            onChange={setEditDuration}
                                                            disabled={
                                                                changeExpiryMutation.isPending
                                                            }
                                                        />
                                                        <div className="flex gap-1">
                                                            <Button
                                                                size="sm"
                                                                className="h-7 text-xs px-2"
                                                                disabled={
                                                                    changeExpiryMutation.isPending
                                                                }
                                                                onClick={() =>
                                                                    changeExpiryMutation.mutate({
                                                                        username:
                                                                            member.discord_username,
                                                                        duration: editDuration,
                                                                    })
                                                                }
                                                            >
                                                                {changeExpiryMutation.isPending
                                                                    ? '…'
                                                                    : 'Save'}
                                                            </Button>
                                                            <Button
                                                                variant="ghost"
                                                                size="sm"
                                                                className="h-7 text-xs px-2"
                                                                onClick={() =>
                                                                    setEditingExpiryId(null)
                                                                }
                                                            >
                                                                Cancel
                                                            </Button>
                                                        </div>
                                                    </div>
                                                ) : confirmRemoveId === member.discord_user_id ? (
                                                    <div className="hidden sm:flex items-center justify-end gap-1">
                                                        <Button
                                                            variant="destructive"
                                                            size="sm"
                                                            onClick={() =>
                                                                removeMutation.mutate(
                                                                    member.discord_user_id
                                                                )
                                                            }
                                                            disabled={removeMutation.isPending}
                                                            className="h-7 text-xs px-2"
                                                        >
                                                            {removeMutation.isPending
                                                                ? '…'
                                                                : 'Remove'}
                                                        </Button>
                                                        <Button
                                                            variant="ghost"
                                                            size="sm"
                                                            onClick={() =>
                                                                setConfirmRemoveId(null)
                                                            }
                                                            className="h-7 text-xs px-2"
                                                        >
                                                            Cancel
                                                        </Button>
                                                    </div>
                                                ) : (
                                                    <div className="flex flex-wrap items-center justify-end gap-1">
                                                        {member.temp_expires_at && (
                                                            <>
                                                                <Button
                                                                    variant="outline"
                                                                    size="sm"
                                                                    className="h-7 text-xs px-2"
                                                                    onClick={() => {
                                                                        setEditDuration(
                                                                            DEFAULT_DURATION_PRESET
                                                                        )
                                                                        setEditingExpiryId(
                                                                            member.discord_user_id
                                                                        )
                                                                    }}
                                                                >
                                                                    Change expiry
                                                                </Button>
                                                                <Button
                                                                    variant="outline"
                                                                    size="sm"
                                                                    className="h-7 text-xs px-2"
                                                                    disabled={
                                                                        makePermanentMutation.isPending
                                                                    }
                                                                    onClick={() =>
                                                                        makePermanentMutation.mutate(
                                                                            member.discord_username
                                                                        )
                                                                    }
                                                                >
                                                                    Make permanent
                                                                </Button>
                                                            </>
                                                        )}
                                                        <Button
                                                            variant="ghost"
                                                            size="icon-sm"
                                                            onClick={() =>
                                                                setConfirmRemoveId(
                                                                    member.discord_user_id
                                                                )
                                                            }
                                                            disabled={removeMutation.isPending}
                                                            className="text-muted-foreground hover:text-destructive hover:bg-destructive/10"
                                                            title={`Remove ${labelLower} role`}
                                                        >
                                                            ✕
                                                        </Button>
                                                    </div>
                                                )}
                                                {confirmRemoveId === member.discord_user_id && (
                                                    <div className="flex sm:hidden justify-end">
                                                        <Button
                                                            variant="ghost"
                                                            size="icon-sm"
                                                            onClick={() =>
                                                                setConfirmRemoveId(null)
                                                            }
                                                            disabled={removeMutation.isPending}
                                                            className="text-muted-foreground hover:text-destructive hover:bg-destructive/10"
                                                            title={`Remove ${labelLower} role`}
                                                        >
                                                            ✕
                                                        </Button>
                                                    </div>
                                                )}
                                            </td>
                                        )}
                                    </tr>
                                    {canManage &&
                                        confirmRemoveId === member.discord_user_id && (
                                            <tr className="sm:hidden bg-destructive/5 border-t border-destructive/20">
                                                <td colSpan={3} className="px-3 py-2">
                                                    <div className="flex items-center gap-2">
                                                        <span className="text-sm text-muted-foreground">
                                                            Remove @{member.discord_username}?
                                                        </span>
                                                        <Button
                                                            variant="destructive"
                                                            size="sm"
                                                            onClick={() =>
                                                                removeMutation.mutate(
                                                                    member.discord_user_id
                                                                )
                                                            }
                                                            disabled={removeMutation.isPending}
                                                            className="h-7 text-xs px-2"
                                                        >
                                                            {removeMutation.isPending
                                                                ? '…'
                                                                : 'Remove'}
                                                        </Button>
                                                        <Button
                                                            variant="ghost"
                                                            size="sm"
                                                            onClick={() =>
                                                                setConfirmRemoveId(null)
                                                            }
                                                            className="h-7 text-xs px-2"
                                                        >
                                                            Cancel
                                                        </Button>
                                                    </div>
                                                </td>
                                            </tr>
                                        )}
                                </Fragment>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}

            {!isLoading && !errorMsg && members.length === 0 && (
                <p className="text-muted-foreground italic p-4 text-center bg-muted/30 rounded-lg">
                    No {labelLower}s found.
                </p>
            )}
        </>
    )
}

function RoleManagement({ canManage }: { canManage: boolean }) {
    const [activeTab, setActiveTab] = useState<TabValue>('drivers')

    return (
        <SectionCard icon={<UserCheck className="h-4 w-4" />} title="Role Management">
            <div className="mb-6">
                <SegmentedControl options={TABS} value={activeTab} onChange={setActiveTab} />
            </div>
            <RolePanel key={activeTab} config={ROLE_CONFIGS[activeTab]} canManage={canManage} />
        </SectionCard>
    )
}

export default RoleManagement
