import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiFetch } from '../lib/api'
import type { AccountRole } from '../types'
import ErrorMessage from './ErrorMessage'
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from './ui/select'
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
    ride_coordinator: 'text-blue-700 dark:text-blue-300',
    viewer: 'text-slate-600 dark:text-slate-400',
}

function UserManagement() {
    const queryClient = useQueryClient()
    const [inviteUsername, setInviteUsername] = useState('')
    const [inviteRole, setInviteRole] = useState<AccountRole>('viewer')
    const [showEmailFor, setShowEmailFor] = useState<Set<number>>(new Set())

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
                <div className="mb-6 p-4 rounded-lg border border-slate-200 dark:border-zinc-800 bg-slate-50 dark:bg-zinc-900/50">
                    <p className="text-sm font-medium text-slate-700 dark:text-slate-300 mb-3">Invite by Discord username</p>
                    <div className="flex flex-col sm:flex-row gap-2">
                        <input
                            type="text"
                            placeholder="Discord username (e.g. johndoe)"
                            value={inviteUsername}
                            onChange={(e) => setInviteUsername(e.target.value)}
                            className="flex-1 px-3 py-2 text-sm rounded-md border border-slate-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
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
                        <button
                            onClick={() => inviteMutation.mutate({ discord_username: inviteUsername.trim(), role: inviteRole })}
                            disabled={!inviteUsername.trim() || inviteMutation.isPending}
                            className="px-4 py-2 text-sm font-medium rounded-md bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white transition-colors"
                        >
                            {inviteMutation.isPending ? 'Inviting…' : 'Invite'}
                        </button>
                    </div>
                </div>

                {!isLoading && !errorMsg && users.length > 0 && (
                    <div className="rounded-lg border border-slate-200 dark:border-zinc-800 overflow-x-auto w-full max-w-[calc(100vw-3rem)]">
                        <table className="w-full text-left text-sm">
                            <thead className="bg-slate-50 dark:bg-zinc-800/50 text-slate-900 dark:text-slate-100 font-semibold border-b border-slate-200 dark:border-zinc-800">
                                <tr>
                                    <th scope="col" className="px-3 sm:px-6 py-3 sm:py-4">User</th>
                                    <th scope="col" className="px-3 sm:px-6 py-3 sm:py-4 w-[160px] sm:w-[220px]">Role</th>
                                    <th scope="col" className="px-3 sm:px-6 py-3 sm:py-4 w-12"></th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-slate-100 dark:divide-zinc-800">
                                {users.map((user) => (
                                    <tr
                                        key={user.id}
                                        className="hover:bg-slate-50 dark:hover:bg-zinc-800/30 transition-colors"
                                    >
                                        <td className="px-3 sm:px-6 py-3 sm:py-4">
                                            {user.discord_username ? (
                                                <span className="text-slate-700 dark:text-slate-300 font-medium">@{user.discord_username}</span>
                                            ) : (
                                                <span className="text-slate-500 dark:text-slate-400 italic">pending login</span>
                                            )}
                                            {user.discord_username && !user.discord_user_id && (
                                                <div className="text-xs text-slate-400 dark:text-slate-500 mt-0.5">not yet logged in</div>
                                            )}
                                            {user.role_edited_by && (
                                                <div className="text-xs text-slate-400 dark:text-slate-500 mt-0.5">
                                                    promoted by {user.role_edited_by}
                                                </div>
                                            )}
                                            {user.invited_by && !user.discord_user_id && (
                                                <div className="text-xs text-slate-400 dark:text-slate-500 mt-0.5">
                                                    invited by {user.invited_by}
                                                </div>
                                            )}
                                            {user.email && (
                                                <div className="mt-0.5">
                                                    <button
                                                        onClick={() => toggleEmail(user.id)}
                                                        className="text-xs text-slate-400 dark:text-slate-500 hover:text-slate-600 dark:hover:text-slate-300 transition-colors"
                                                    >
                                                        {showEmailFor.has(user.id) ? 'hide email' : 'show email'}
                                                    </button>
                                                    {showEmailFor.has(user.id) && (
                                                        <div className="text-xs text-slate-500 dark:text-slate-400 break-all mt-0.5">{user.email}</div>
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
                                            <button
                                                onClick={() => {
                                                    if (window.confirm(`Remove ${user.email ?? user.discord_username ?? 'this user'}?`)) {
                                                        revokeMutation.mutate(user.id)
                                                    }
                                                }}
                                                disabled={
                                                    revokeMutation.isPending ||
                                                    (user.email ? (user.email === data?.current_user_email || data?.admin_emails.includes(user.email)) : false)
                                                }
                                                className="text-slate-400 hover:text-red-600 dark:hover:text-red-400 disabled:opacity-30 transition-colors text-xs"
                                                title="Revoke access"
                                            >
                                                ✕
                                            </button>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                )}

                {!isLoading && !errorMsg && users.length === 0 && (
                    <p className="text-slate-500 italic p-4 text-center bg-slate-50 dark:bg-zinc-800/50 rounded-lg">
                        No users found.
                    </p>
                )}
        </SectionCard>
    )
}

export default UserManagement
