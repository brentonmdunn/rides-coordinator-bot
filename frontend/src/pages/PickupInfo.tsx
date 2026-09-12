/**
 * PickupInfo.tsx
 *
 * Pickup info management page — names, Discord usernames, class year,
 * and where they live. Editable by admins and ride coordinators (mirrors
 * the backend's require_ride_coordinator gate on /api/pickup-info).
 */

import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '../lib/api'
import type { AccountRole } from '../types'
import PickupInfoManager from '../components/PickupInfo/PickupInfoManager'
import { BackLink, PageHeader, PageLayout } from '../components/shared'
import { ModeToggle } from '../components/mode-toggle'
import { GridSkeleton } from '../components/LoadingSkeleton'

function PickupInfo() {
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
                    title="Pickup Info"
                    description="People we give rides to: names, Discord usernames, class year, and where they live."
                    actions={<ModeToggle />}
                />
            }
        >
            {isLoading ? (
                <GridSkeleton count={6} />
            ) : canManage ? (
                <PickupInfoManager />
            ) : (
                <div className="rounded-lg border border-warning/30 bg-warning/10 px-4 py-3 text-sm text-warning-text">
                    You need the ride coordinator or admin role to manage the pickupInfo. Ask an
                    admin to grant you access from the dashboard's Roles section.
                </div>
            )}
        </PageLayout>
    )
}

export default PickupInfo
