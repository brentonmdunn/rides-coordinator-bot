import { Suspense, lazy } from 'react'
import { Link } from 'react-router-dom'
import { BookOpen, MessageSquare } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '../lib/api'
import type { AccountRole } from '../types'
import PickupLocations from '../components/PickupLocations'
import DriverReactions from '../components/DriverReactions'
import ReactionDetails from '../components/ReactionDetails'
import GroupRides from '../components/GroupRides'
import RouteBuilder from '../components/RouteBuilder/RouteBuilder'
import MapLinks from '../components/MapLinks'
import AskRidesDashboard from '../components/AskRidesDashboard/AskRidesDashboard'
import RideCoverageCheck from '../components/RideCoverageCheck'
import RideCoverageWarning from '../components/RideCoverageWarning'
import RoleSwitcher from '../components/RoleSwitcher'
import { ModeToggle } from '../components/mode-toggle'
import { PageHeader, PageLayout } from '../components/shared'

const FeatureFlagsManager = lazy(() => import('../components/FeatureFlagsManager'))
const UserManagement = lazy(() => import('../components/UserManagement'))
const SystemActions = lazy(() => import('../components/SystemActions'))

function Home() {
    const { data: meData } = useQuery<{ email: string; role: AccountRole; is_local: boolean }>({
        queryKey: ['me'],
        queryFn: async () => {
            const res = await apiFetch('/api/me')
            return res.json()
        },
    })

    const role = meData?.role ?? 'viewer'
    const isLocal = meData?.is_local ?? false
    const isAdmin = role === 'admin'
    const canManage = role === 'admin' || role === 'ride_coordinator'

    return (
        <>
            {isLocal && <RoleSwitcher currentRole={role} />}
            <PageLayout
                spacedBody
                header={
                    <PageHeader
                        centerOnMobile
                        title="🚗 Admin Dashboard"
                        description="Manage rides, view pickups, and configure bot settings all in one place."
                        actions={
                            <>
                                {canManage && (
                                    <Link
                                        to="/modmail"
                                        className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-slate-700 dark:text-slate-200 bg-white dark:bg-zinc-800 border border-slate-200 dark:border-zinc-700 rounded-lg hover:bg-slate-50 dark:hover:bg-zinc-700 transition-colors"
                                    >
                                        <MessageSquare className="w-4 h-4" />
                                        Modmail
                                    </Link>
                                )}
                                <Link
                                    to="/learn"
                                    className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-slate-700 dark:text-slate-200 bg-white dark:bg-zinc-800 border border-slate-200 dark:border-zinc-700 rounded-lg hover:bg-slate-50 dark:hover:bg-zinc-700 transition-colors"
                                >
                                    <BookOpen className="w-4 h-4" />
                                    Learn
                                </Link>
                                <ModeToggle />
                            </>
                        }
                    />
                }
            >
                <div className="grid gap-8">
                    <RideCoverageWarning />
                    <AskRidesDashboard canManage={canManage} />
                    <ReactionDetails />
                    <DriverReactions />
                    <RideCoverageCheck />
                    <PickupLocations />
                    <GroupRides />
                    <RouteBuilder />
                    <MapLinks />
                    {isAdmin && (
                        <Suspense fallback={<div className="text-center py-8 text-slate-500">Loading admin tools…</div>}>
                            <FeatureFlagsManager />
                            <UserManagement />
                            <SystemActions />
                        </Suspense>
                    )}
                </div>
            </PageLayout>
        </>
    )
}

export default Home
