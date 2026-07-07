import { Suspense, lazy, useMemo, useState } from 'react'
import ErrorBoundary from '../components/ErrorBoundary'
import { Link } from 'react-router-dom'
import { BookOpen, Car, History, MapPin, Users, Map, Shield, CalendarDays, ClipboardList, Target, Navigation, UserCheck, UserPlus, Settings } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '../lib/api'
import type { AccountRole } from '../types'
import PickupLocations from '../components/PickupLocations'
import NonDiscordRides from '../components/NonDiscordRides'
import DriverReactions from '../components/DriverReactions'
import ReactionDetails from '../components/ReactionDetails'
import GroupRides from '../components/GroupRides'
import RouteBuilder from '../components/RouteBuilder/RouteBuilder'
import MapLinks from '../components/MapLinks'
import RoleManagement from '../components/RoleManagement'
import AskRidesDashboard from '../components/AskRidesDashboard/AskRidesDashboard'
import RideCoverageCheck from '../components/RideCoverageCheck'
import RideCoverageWarning from '../components/RideCoverageWarning'
import RoleSwitcher from '../components/RoleSwitcher'
import { ModeToggle } from '../components/mode-toggle'
import SiteSettingsDialog from '../components/SiteSettingsDialog'
import { PageHeader, PageLayout } from '../components/shared'
import { Button } from '../components/ui/button'
import { CollapsibleSection } from '../components/ui/collapsible'
import { logout } from '../lib/auth'
import { useActiveSection } from '../hooks/useActiveSection'
import { cn } from '../lib/utils'

const FeatureFlagsManager = lazy(() => import('../components/FeatureFlagsManager'))
const UserManagement = lazy(() => import('../components/UserManagement'))
const SystemActions = lazy(() => import('../components/SystemActions'))

const NAV_ITEMS = [
    { id: 'ask-rides', label: 'Ask Rides', icon: <CalendarDays className="h-4 w-4" /> },
    { id: 'reactions', label: 'Reactions', icon: <ClipboardList className="h-4 w-4" /> },
    { id: 'driver-reactions', label: 'Driver Reactions', icon: <Car className="h-4 w-4" /> },
    { id: 'ride-coverage', label: 'Coverage', icon: <Target className="h-4 w-4" /> },
    { id: 'pickup-locations', label: 'Pickups', icon: <MapPin className="h-4 w-4" /> },
    { id: 'group-rides', label: 'Group Rides', icon: <Users className="h-4 w-4" /> },
    { id: 'route-builder', label: 'Route Builder', icon: <Map className="h-4 w-4" /> },
    { id: 'map-links', label: 'Map Links', icon: <Navigation className="h-4 w-4" /> },
    { id: 'roles', label: 'Roles', icon: <UserCheck className="h-4 w-4" /> },
]

function SectionNav({ isAdmin, canManage }: { isAdmin: boolean; canManage: boolean }) {
    const items = useMemo(() => {
        let result = NAV_ITEMS
        if (canManage) {
            const pickupsIdx = result.findIndex((item) => item.id === 'pickup-locations')
            const nonDiscordItem = {
                id: 'non-discord-rides',
                label: 'Non-Discord',
                icon: <UserPlus className="h-4 w-4" />,
            }
            result = [
                ...result.slice(0, pickupsIdx + 1),
                nonDiscordItem,
                ...result.slice(pickupsIdx + 1),
            ]
        }
        if (isAdmin) {
            result = [
                ...result,
                { id: 'admin', label: 'Admin', icon: <Shield className="h-4 w-4" /> },
            ]
        }
        return result
    }, [isAdmin, canManage])

    const activeId = useActiveSection(items.map((item) => item.id))

    return (
        <aside className="hidden xl:block w-44 shrink-0">
            <nav className="sticky top-8 space-y-0.5">
                <p className="text-xs font-semibold text-muted-foreground uppercase tracking-widest px-3 mb-3">
                    Sections
                </p>
                {items.map((item) => {
                    const isActive = activeId === item.id
                    return (
                        <a
                            key={item.id}
                            href={`#${item.id}`}
                            className={cn(
                                'flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm transition-colors',
                                isActive
                                    ? 'bg-accent/10 text-foreground font-medium'
                                    : 'text-muted-foreground hover:text-foreground hover:bg-muted/50'
                            )}
                        >
                            {item.icon}
                            <span>{item.label}</span>
                            {isActive && (
                                <span className="ml-auto w-1.5 h-1.5 rounded-full bg-accent shrink-0" />
                            )}
                        </a>
                    )
                })}
            </nav>
        </aside>
    )
}

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

    const [showSiteSettings, setShowSiteSettings] = useState(false)

    return (
        <>
            {isLocal && <RoleSwitcher currentRole={role} />}
            <PageLayout
                spacedBody
                header={
                    <PageHeader
                        centerOnMobile
                        title="Admin Dashboard"
                        description="Manage rides, view pickups, and configure bot settings all in one place."
                        actions={
                            <div className="flex flex-col items-center md:items-end gap-2">
                                <div className="flex flex-wrap items-center justify-center md:justify-end gap-2">
                                    {canManage && (
                                        <Button variant="outline" size="sm" asChild>
                                            <Link to="/locations">
                                                <MapPin className="w-4 h-4" />
                                                Locations
                                            </Link>
                                        </Button>
                                    )}
                                    <Button variant="outline" size="sm" asChild>
                                        <Link to="/reaction-log">
                                            <History className="w-4 h-4" />
                                            Reaction Log
                                        </Link>
                                    </Button>
                                    <Button variant="outline" size="sm" asChild>
                                        <Link to="/learn">
                                            <BookOpen className="w-4 h-4" />
                                            Learn
                                        </Link>
                                    </Button>
                                    <ModeToggle />
                                    <Button
                                        variant="ghost"
                                        size="icon"
                                        onClick={() => setShowSiteSettings(true)}
                                        title="Site settings"
                                    >
                                        <Settings className="h-4 w-4" />
                                        <span className="sr-only">Site settings</span>
                                    </Button>
                                </div>
                                {!isLocal && (
                                    <Button
                                        variant="ghost"
                                        size="sm"
                                        onClick={() => logout()}
                                        title={meData?.email ?? ''}
                                        className="text-xs text-muted-foreground"
                                    >
                                        Sign out ({meData?.email})
                                    </Button>
                                )}
                            </div>
                        }
                    />
                }
            >
                <div className="flex gap-8">
                    <SectionNav isAdmin={isAdmin} canManage={canManage} />

                    <div className="flex-1 min-w-0 grid grid-cols-1 gap-8">
                        <RideCoverageWarning />

                        <div id="ask-rides">
                            <AskRidesDashboard canManage={canManage} />
                        </div>

                        <div id="reactions">
                            <ReactionDetails />
                        </div>

                        <div id="driver-reactions">
                            <DriverReactions />
                        </div>

                        <div id="ride-coverage">
                            <RideCoverageCheck />
                        </div>

                        <div id="pickup-locations">
                            <PickupLocations />
                        </div>

                        {canManage && (
                            <div id="non-discord-rides">
                                <NonDiscordRides />
                            </div>
                        )}

                        <div id="group-rides">
                            <GroupRides />
                        </div>

                        <div id="route-builder">
                            <RouteBuilder />
                        </div>

                        <div id="map-links">
                            <MapLinks />
                        </div>

                        <div id="roles">
                            <RoleManagement canManage={canManage} />
                        </div>

                        {isAdmin && (
                            <div id="admin">
                                <CollapsibleSection title="Admin Tools">
                                    <div className="p-4 space-y-4">
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
                                    </div>
                                </CollapsibleSection>
                            </div>
                        )}
                    </div>
                </div>
            </PageLayout>
            <SiteSettingsDialog
                open={showSiteSettings}
                onOpenChange={setShowSiteSettings}
                canManage={canManage}
            />
        </>
    )
}

export default Home
