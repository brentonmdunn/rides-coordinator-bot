import './App.css'
// import Header from './components/Header'
import PickupLocations from './components/PickupLocations'
import DriverReactions from './components/DriverReactions'
import GroupRides from './components/GroupRides'
// import DemoControls from './components/DemoControls'
import AskRidesDashboard from './components/AskRidesDashboard/AskRidesDashboard'
import RideCoverageCheck from './components/RideCoverageCheck'
import RideCoverageWarning from './components/RideCoverageWarning'
import FeatureFlagsManager from './components/FeatureFlagsManager'
import { ModeToggle } from './components/mode-toggle'

function App() {
  return (
    <div className="min-h-screen w-full overflow-x-hidden bg-gray-50 dark:bg-zinc-950 py-12 px-0 font-sans text-slate-900 dark:text-slate-100 transition-colors duration-300">
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
          <div className="flex justify-center md:justify-end">
            <ModeToggle />
          </div>
        </header>

        <div className="grid gap-8">
          <RideCoverageWarning />
          <AskRidesDashboard />
          <DriverReactions />
          <RideCoverageCheck />
          <PickupLocations />
          <GroupRides />
          <FeatureFlagsManager />
        </div>
      </div>
    </div>
  )
}

export default App
