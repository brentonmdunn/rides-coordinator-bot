import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiFetch } from '../lib/api'
import type { AccountRole } from '../types'
import ErrorMessage from './ErrorMessage'
import { Button } from './ui/button'
import { Input } from './ui/input'
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from './ui/select'
import ConfirmDialog from './ConfirmDialog'
import { TableSkeleton } from './LoadingSkeleton'
import { SectionCard } from './shared'

interface UserAccount {
    id: number
    email: string | null
    discord_username: string | null
    discord_user_id: string | null
    role: AccountRole
    role_edited_by: string | null
    invited_by: string | null
    created_at: string | null
}

interface UsersResponse {
    users: UserAccount[]
    current_user_email: string
    admin_emails: string[]
}

const ROLES: { value: AccountRole; label: string }[] = [
    { value: 'admin', label: '🔑 Admin' },
    { value: 'ride_coordinator', label: '🚗 Ride Coordinator' },
    { value: 'viewer', label: '👁️ Viewer' },
]

const ROLE_COLORS: Record<AccountRole, string> = {
    admin: 'text-purple-700 dark:text-purple-300',
    ride_coordinator: 'text-info-text',
    viewer: 'text-muted-foreground',
}

function UserManagement() {
    const queryClient = useQueryClient()
    const [inviteUsername, setInviteUsername] = useState('')
    const [inviteRole, setInviteRole] = useState<AccountRole>('viewer')
    const [showEmailFor, setShowEmailFor] = useState<Set<number>>(new Set())
    const [revokeTarget, setRevokeTarget] = useState<UserAccount | null>(null)

    const toggleEmail = (id: number) => {
        setShowEmailFor(prev => {
            const next = new Set(prev)
            if (next.has(id)) next.delete(id)
            else next.add(id)
            return next
        })
    }

    const { data, isLoading, error } = useQuery<UsersResponse>({
        queryKey: ['adminUsers'],
        queryFn: async () => {
            const res = await apiFetch('/api/admin/users')
            return res.json()
        },
    })

    const updateRoleMutation = useMutation({
        mutationFn: async ({ email, role }: { email: string; role: string }) => {
            const res = await apiFetch(`/api/admin/users/${encodeURIComponent(email)}/role`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ role }),
            })
            return res.json()
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['adminUsers'] })
            queryClient.invalidateQueries({ queryKey: ['me'] })
        },
    })

    const inviteMutation = useMutation({
        mutationFn: async ({ discord_username, role }: { discord_username: string; role: string }) => {
            const res = await apiFetch('/api/admin/users/invite', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ discord_username, role }),
            })
            return res.json()
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['adminUsers'] })
            setInviteUsername('')
            setInviteRole('viewer')
        },
    })

    const revokeMutation = useMutation({
        mutationFn: async (accountId: number) => {
            const res = await apiFetch(`/api/admin/users/${accountId}`, { method: 'DELETE' })
            return res.json()
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['adminUsers'] })
        },
    })

    const handleRevokeConfirm = () => {
        if (revokeTarget) {
            revokeMutation.mutate(revokeTarget.id)
        }
        setRevokeTarget(null)
    }

    const users = data?.users ?? []
    const errorMsg = error instanceof Error ? error.message : ''

    return (
        <SectionCard icon="👥" title="User Management">
                {isLoading && <TableSkeleton rows={3} cols={3} />}

                <div className="mb-6">
                    <ErrorMessage message={errorMsg} />
                </div>

                {(updateRoleMutation.isError || inviteMutation.isError || revokeMutation.isError) && (
                    <div className="mb-4 px-3 py-2 rounded-md bg-destructive/15 border border-destructive/30 text-destructive-text text-sm">
                        ❌ {[updateRoleMutation.error, inviteMutation.error, revokeMutation.error]
                            .find(Boolean) instanceof Error
                            ? ([updateRoleMutation.error, inviteMutation.error, revokeMutation.error].find(Boolean) as Error).message
                            : 'Operation failed'}
                    </div>
                )}

                {/* Invite form */}
                <div className="mb-6 p-4 rounded-lg border border-border bg-muted/30">
                    <p className="text-sm font-medium text-foreground mb-3">Invite by Discord username</p>
                    <div className="flex flex-col sm:flex-row gap-2">
                        <Input
                            type="text"
                            placeholder="Discord username (e.g. johndoe)"
                            value={inviteUsername}
                            onChange={(e) => setInviteUsername(e.target.value)}
                            className="flex-1"
                        />
                        <Select value={inviteRole} onValueChange={(v) => setInviteRole(v as AccountRole)}>
                            <SelectTrigger className={`w-full sm:w-[180px] font-medium ${ROLE_COLORS[inviteRole]}`}>
                                <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                                {ROLES.map((r) => (
                                    <SelectItem key={r.value} value={r.value}>{r.label}</SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                        <Button
                            onClick={() => inviteMutation.mutate({ discord_username: inviteUsername.trim(), role: inviteRole })}
                            disabled={!inviteUsername.trim() || inviteMutation.isPending}
                        >
                            {inviteMutation.isPending ? 'Inviting…' : 'Invite'}
                        </Button>
                    </div>
                </div>

                {!isLoading && !errorMsg && users.length > 0 && (
                    <div className="rounded-lg border border-border overflow-x-auto w-full max-w-[calc(100vw-3rem)]">
                        <table className="w-full text-left text-sm">
                            <thead className="bg-muted/50 text-foreground font-semibold border-b border-border">
                                <tr>
                                    <th scope="col" className="px-3 sm:px-6 py-3 sm:py-4">User</th>
                                    <th scope="col" className="px-3 sm:px-6 py-3 sm:py-4 w-[160px] sm:w-[220px]">Role</th>
                                    <th scope="col" className="px-3 sm:px-6 py-3 sm:py-4 w-12"></th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-border">
                                {users.map((user) => (
                                    <tr
                                        key={user.id}
                                        className="hover:bg-muted/30 transition-colors"
                                    >
                                        <td className="px-3 sm:px-6 py-3 sm:py-4">
                                            {user.discord_username ? (
                                                <span className="text-foreground font-medium">@{user.discord_username}</span>
                                            ) : (
                                                <span className="text-muted-foreground italic">pending login</span>
                                            )}
                                            {user.discord_username && !user.discord_user_id && (
                                                <div className="text-xs text-muted-foreground mt-0.5">not yet logged in</div>
                                            )}
                                            {user.role_edited_by && (
                                                <div className="text-xs text-muted-foreground mt-0.5">
                                                    promoted by {user.role_edited_by}
                                                </div>
                                            )}
                                            {user.invited_by && !user.discord_user_id && (
                                                <div className="text-xs text-muted-foreground mt-0.5">
                                                    invited by {user.invited_by}
                                                </div>
                                            )}
                                            {user.email && (
                                                <div className="mt-0.5">
                                                    <Button
                                                        variant="ghost"
                                                        size="sm"
                                                        onClick={() => toggleEmail(user.id)}
                                                        className="h-auto p-0 text-xs text-muted-foreground hover:text-foreground font-normal"
                                                    >
                                                        {showEmailFor.has(user.id) ? 'hide email' : 'show email'}
                                                    </Button>
                                                    {showEmailFor.has(user.id) && (
                                                        <div className="text-xs text-muted-foreground break-all mt-0.5">{user.email}</div>
                                                    )}
                                                </div>
                                            )}
                                        </td>
                                        <td className="px-3 sm:px-6 py-3 sm:py-4">
                                            <Select
                                                value={user.role}
                                                onValueChange={(val) => {
                                                    if (user.email) {
                                                        updateRoleMutation.mutate({ email: user.email, role: val })
                                                    }
                                                }}
                                                disabled={
                                                    updateRoleMutation.isPending ||
                                                    !user.email ||
                                                    user.email === data?.current_user_email ||
                                                    (user.email ? data?.admin_emails.includes(user.email) : false)
                                                }
                                            >
                                                <SelectTrigger className={`w-full font-medium ${ROLE_COLORS[user.role]}`}>
                                                    <SelectValue />
                                                </SelectTrigger>
                                                <SelectContent>
                                                    {ROLES.map((r) => (
                                                        <SelectItem key={r.value} value={r.value}>
                                                            {r.label}
                                                        </SelectItem>
                                                    ))}
                                                </SelectContent>
                                            </Select>
                                        </td>
                                        <td className="px-3 sm:px-6 py-3 sm:py-4">
                                            <Button
                                                variant="ghost"
                                                size="icon-sm"
                                                onClick={() => setRevokeTarget(user)}
                                                disabled={
                                                    revokeMutation.isPending ||
                                                    (user.email ? (user.email === data?.current_user_email || data?.admin_emails.includes(user.email)) : false)
                                                }
                                                className="text-muted-foreground hover:text-destructive hover:bg-destructive/10"
                                                title="Revoke access"
                                            >
                                                ✕
                                            </Button>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                )}

                {!isLoading && !errorMsg && users.length === 0 && (
                    <p className="text-muted-foreground italic p-4 text-center bg-muted/30 rounded-lg">
                        No users found.
                    </p>
                )}

                <ConfirmDialog
                    isOpen={revokeTarget !== null}
                    title="Remove user?"
                    description={`Remove ${revokeTarget?.email ?? revokeTarget?.discord_username ?? 'this user'}? They will lose all access.`}
                    confirmText="Remove"
                    confirmVariant="destructive"
                    onConfirm={handleRevokeConfirm}
                    onCancel={() => setRevokeTarget(null)}
                />
        </SectionCard>
    )
}

export default UserManagement
