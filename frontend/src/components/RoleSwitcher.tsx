import { useMutation, useQueryClient } from '@tanstack/react-query'
import { apiFetch } from '../lib/api'
import type { AccountRole } from '../types'

const ROLES: { value: AccountRole; label: string; description: string }[] = [
    { value: 'admin', label: '🔑 Admin', description: 'Full access' },
    { value: 'ride_coordinator', label: '🚗 Ride Coordinator', description: 'Manage rides' },
    { value: 'viewer', label: '👁️ Viewer', description: 'Read only' },
]

interface RoleSwitcherProps {
    currentRole: AccountRole
}

function RoleSwitcher({ currentRole }: RoleSwitcherProps) {
    const queryClient = useQueryClient()

    const switchRoleMutation = useMutation({
        mutationFn: async (role: AccountRole) => {
            const res = await apiFetch('/api/me/role', {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ role }),
            })
            if (!res.ok) throw new Error('Failed to switch role')
            return res.json()
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['me'] })
        },
    })

    const currentRoleInfo = ROLES.find(r => r.value === currentRole)

    return (
        <div className="w-full bg-gradient-to-r from-amber-500 via-amber-400 to-orange-400 dark:from-amber-600 dark:via-amber-500 dark:to-orange-500">
            <div className="max-w-4xl mx-auto px-4 py-2 flex items-center justify-between gap-4">
                <div className="flex items-center gap-2 text-amber-950 dark:text-amber-50">
                    <span className="text-sm font-semibold tracking-wide uppercase opacity-80">
                        Dev Mode
                    </span>
                    <span className="text-xs opacity-60">—</span>
                    <span className="text-sm">
                        Viewing as <strong>{currentRoleInfo?.label ?? currentRole}</strong>
                    </span>
                </div>
                <div className="flex items-center gap-1.5">
                    {ROLES.map((r) => (
                        <button
                            key={r.value}
                            onClick={() => switchRoleMutation.mutate(r.value)}
                            disabled={switchRoleMutation.isPending || r.value === currentRole}
                            className={`
                                px-3 py-1 rounded-full text-xs font-medium transition-all
                                ${r.value === currentRole
                                    ? 'bg-white/90 dark:bg-zinc-900/80 text-amber-900 dark:text-amber-100 shadow-sm cursor-default'
                                    : 'bg-white/30 dark:bg-white/10 text-amber-950 dark:text-amber-50 hover:bg-white/60 dark:hover:bg-white/20 cursor-pointer'
                                }
                                disabled:opacity-50
                            `}
                            title={r.description}
                        >
                            {r.label}
                        </button>
                    ))}
                </div>
            </div>
        </div>
    )
}

export default RoleSwitcher
