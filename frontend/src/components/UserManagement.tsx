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

import { Card, CardHeader, CardTitle, CardContent } from './ui/card'

interface UserAccount {
    id: number
    email: string
    role: AccountRole
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

    const { data, isLoading, error } = useQuery<UsersResponse>({
        queryKey: ['adminUsers'],
        queryFn: async () => {
            const res = await apiFetch('/api/admin/users')
            if (!res.ok) throw new Error('Failed to load users')
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
            if (!res.ok) {
                const data = await res.json().catch(() => ({}))
                throw new Error(data.detail || 'Failed to update role')
            }
            return res.json()
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['adminUsers'] })
            queryClient.invalidateQueries({ queryKey: ['me'] })
        },
    })

    const users = data?.users ?? []
    const errorMsg = error instanceof Error ? error.message : ''

    return (
        <Card>
            <CardHeader>
                <CardTitle className="flex items-center gap-2">
                    <span>👥</span>
                    <span>User Management</span>
                </CardTitle>
            </CardHeader>
            <CardContent>
                {isLoading && (
                    <div className="p-8 text-center text-slate-500 animate-pulse">
                        Loading users...
                    </div>
                )}

                <div className="mb-6">
                    <ErrorMessage message={errorMsg} />
                </div>

                {updateRoleMutation.isError && (
                    <div className="mb-4 px-3 py-2 rounded-md bg-destructive/15 border border-destructive/30 text-destructive-text text-sm">
                        ❌ {updateRoleMutation.error instanceof Error ? updateRoleMutation.error.message : 'Failed to update role'}
                    </div>
                )}

                {!isLoading && !errorMsg && users.length > 0 && (
                    <div className="rounded-lg border border-slate-200 dark:border-zinc-800 overflow-x-auto w-full max-w-[calc(100vw-3rem)]">
                        <table className="w-full text-left text-sm">
                            <thead className="bg-slate-50 dark:bg-zinc-800/50 text-slate-900 dark:text-slate-100 font-semibold border-b border-slate-200 dark:border-zinc-800">
                                <tr>
                                    <th className="px-6 py-4">Email</th>
                                    <th className="px-6 py-4 w-[220px]">Role</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-slate-100 dark:divide-zinc-800">
                                {users.map((user) => (
                                    <tr
                                        key={user.id}
                                        className="hover:bg-slate-50 dark:hover:bg-zinc-800/30 transition-colors"
                                    >
                                        <td className="px-6 py-4 text-slate-700 dark:text-slate-300">
                                            {user.email}
                                        </td>
                                        <td className="px-6 py-4">
                                            <Select
                                                value={user.role}
                                                onValueChange={(val) =>
                                                    updateRoleMutation.mutate({
                                                        email: user.email,
                                                        role: val,
                                                    })
                                                }
                                                disabled={
                                                    updateRoleMutation.isPending ||
                                                    user.email === data?.current_user_email ||
                                                    data?.admin_emails.includes(user.email)
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
            </CardContent>
        </Card>
    )
}

export default UserManagement
