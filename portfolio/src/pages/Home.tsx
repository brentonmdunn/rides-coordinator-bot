import { Suspense, lazy } from 'react'
import ErrorBoundary from '../components/ErrorBoundary'
import { Link } from 'react-router-dom'
import { BookOpen, History } from 'lucide-react'
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

    const role = meData?.role ?? 'admin'
    const isAdmin = role === 'admin'
    const canManage = role === 'admin' || role === 'ride_coordinator'

    return (
        <PageLayout
            spacedBody
            header={
                <PageHeader
                    centerOnMobile
                    title="Admin Dashboard"
                    description="Manage rides, view pickups, and configure bot settings all in one place."
                    actions={
                        <div className="flex flex-wrap justify-center md:justify-end gap-2">
                            <Link
                                to="/reaction-log"
                                className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-foreground bg-card border border-border rounded-lg hover:bg-muted transition-colors"
                            >
                                <History className="w-4 h-4" />
                                Reaction Log
                            </Link>
                            <Link
                                to="/learn"
                                className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-foreground bg-card border border-border rounded-lg hover:bg-muted transition-colors"
                            >
                                <BookOpen className="w-4 h-4" />
                                Learn
                            </Link>
                            <ModeToggle />
                        </div>
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
                    <>
                        <ErrorBoundary fallback={<div className="rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive-text">Feature flags unavailable</div>}>
                            <Suspense fallback={<div className="text-center py-8 text-muted-foreground">Loading…</div>}>
                                <FeatureFlagsManager />
                            </Suspense>
                        </ErrorBoundary>
                        <ErrorBoundary fallback={<div className="rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive-text">User management unavailable</div>}>
                            <Suspense fallback={<div className="text-center py-8 text-muted-foreground">Loading…</div>}>
                                <UserManagement />
                            </Suspense>
                        </ErrorBoundary>
                        <ErrorBoundary fallback={<div className="rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive-text">System actions unavailable</div>}>
                            <Suspense fallback={<div className="text-center py-8 text-muted-foreground">Loading…</div>}>
                                <SystemActions />
                            </Suspense>
                        </ErrorBoundary>
                    </>
                )}
            </div>
        </PageLayout>
    )
}

export default Home
