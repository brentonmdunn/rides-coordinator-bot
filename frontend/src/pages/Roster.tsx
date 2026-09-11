/**
 * Roster.tsx
 *
 * People-roster management page — names, Discord usernames, class year,
 * and where they live. Editable by admins and ride coordinators (mirrors
 * the backend's require_ride_coordinator gate on /api/roster).
 */

import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '../lib/api'
import type { AccountRole } from '../types'
import RosterManager from '../components/Roster/RosterManager'
import { BackLink, PageHeader, PageLayout } from '../components/shared'
import { ModeToggle } from '../components/mode-toggle'
import { GridSkeleton } from '../components/LoadingSkeleton'

function Roster() {
    const { data: meData, isLoading } = useQuery<{
        email: string
        role: AccountRole
        is_local: boolean
    }>({
        queryKey: ['me'],
        queryFn: async () => {
            const res = await apiFetch('/api/me')
            return res.json()
        },
    })

    const role = meData?.role ?? 'viewer'
    const canManage = role === 'admin' || role === 'ride_coordinator'

    return (
        <PageLayout
            spacedBody
            header={
                <PageHeader
                    eyebrow={<BackLink to="/" />}
                    title="Roster"
                    description="People we give rides to: names, Discord usernames, class year, and where they live."
                    actions={<ModeToggle />}
                />
            }
        >
            {isLoading ? (
                <GridSkeleton count={6} />
            ) : canManage ? (
                <RosterManager />
            ) : (
                <div className="rounded-lg border border-warning/30 bg-warning/10 px-4 py-3 text-sm text-warning-text">
                    You need the ride coordinator or admin role to manage the roster. Ask an
                    admin to grant you access from the dashboard's Roles section.
                </div>
            )}
        </PageLayout>
    )
}

export default Roster
