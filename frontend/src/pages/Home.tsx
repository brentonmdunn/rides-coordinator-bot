import { Link } from 'react-router-dom'
import { BookOpen } from 'lucide-react'
import PickupLocations from '../components/PickupLocations'
import DriverReactions from '../components/DriverReactions'
import ReactionDetails from '../components/ReactionDetails'
import GroupRides from '../components/GroupRides'
import RouteBuilder from '../components/RouteBuilder'
import AskRidesDashboard from '../components/AskRidesDashboard/AskRidesDashboard'
import RideCoverageCheck from '../components/RideCoverageCheck'
import RideCoverageWarning from '../components/RideCoverageWarning'
import FeatureFlagsManager from '../components/FeatureFlagsManager'
import { ModeToggle } from '../components/mode-toggle'
import EnvironmentBanner from '../components/EnvironmentBanner'

function Home() {
    return (
        <>
            <EnvironmentBanner />
            <div className="min-h-screen w-full max-w-[100vw] overflow-x-hidden bg-gray-50 dark:bg-zinc-950 py-12 px-4 font-sans text-slate-900 dark:text-slate-100 transition-colors duration-300">
                <div className="max-w-4xl mx-auto space-y-8 overflow-x-hidden">
                    <header className="flex flex-col md:flex-row md:items-start md:justify-between gap-6 mb-12">
                        <div className="flex-1 text-center md:text-left">
                            <h1 className="text-4xl font-extrabold tracking-tight text-slate-900 dark:text-white sm:text-5xl mb-4">
                                🚗 Admin Dashboard
                            </h1>
                            <p className="text-lg text-slate-600 dark:text-slate-400 max-w-2xl mx-auto md:mx-0">
                                Manage rides, view pickups, and configure bot settings all in one place.
                            </p>
                        </div>
                        <div className="flex items-center gap-3 justify-center md:justify-end">
                            <Link
                                to="/learn"
                                className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-slate-700 dark:text-slate-200 bg-white dark:bg-zinc-800 border border-slate-200 dark:border-zinc-700 rounded-lg hover:bg-slate-50 dark:hover:bg-zinc-700 transition-colors"
                            >
                                <BookOpen className="w-4 h-4" />
                                Learn
                            </Link>
                            <ModeToggle />
                        </div>
                    </header>

                    <div className="grid gap-8">
                        <RideCoverageWarning />
                        <AskRidesDashboard />
                        <ReactionDetails />
                        <DriverReactions />
                        <RideCoverageCheck />
                        <PickupLocations />
                        <GroupRides />
                        <RouteBuilder />
                        <FeatureFlagsManager />
                    </div>
                </div>
            </div>
        </>
    )
}

export default Home
