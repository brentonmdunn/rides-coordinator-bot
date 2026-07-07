/**
 * Locations.tsx
 *
 * Pickup-location management page — map, location table, travel times and
 * settings. Editable by admins and ride coordinators (mirrors the backend's
 * require_ride_coordinator gate on /api/pickup-locations).
 */

import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '../lib/api'
import type { AccountRole } from '../types'
import LocationManager from '../components/LocationManager/LocationManager'
import { BackLink, PageHeader, PageLayout } from '../components/shared'
import { ModeToggle } from '../components/mode-toggle'
import { GridSkeleton } from '../components/LoadingSkeleton'

function Locations() {
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
                    title="Locations"
                    description="Manage pickup locations, GPS coordinates, travel times between stops, and how campus living areas map to pickup spots."
                    actions={<ModeToggle />}
                />
            }
        >
            {isLoading ? (
                <GridSkeleton count={6} />
            ) : canManage ? (
                <LocationManager />
            ) : (
                <div className="rounded-lg border border-warning/30 bg-warning/10 px-4 py-3 text-sm text-warning-text">
                    You need the ride coordinator or admin role to manage locations. Ask an
                    admin to grant you access from the dashboard's Roles section.
                </div>
            )}
        </PageLayout>
    )
}

export default Locations
