import './App.css'
// import Header from './components/Header'
import PickupLocations from './components/PickupLocations'
import DriverReactions from './components/DriverReactions'
import ReactionDetails from './components/ReactionDetails'
import GroupRides from './components/GroupRides'
import RouteBuilder from './components/RouteBuilder'
// import DemoControls from './components/DemoControls'
import AskRidesDashboard from './components/AskRidesDashboard/AskRidesDashboard'
import RideCoverageCheck from './components/RideCoverageCheck'
import RideCoverageWarning from './components/RideCoverageWarning'
import FeatureFlagsManager from './components/FeatureFlagsManager'
import { ModeToggle } from './components/mode-toggle'
import EnvironmentBanner from './components/EnvironmentBanner'

function App() {
  return (
    <>
      <EnvironmentBanner />
      <div className="min-h-screen w-full max-w-[100vw] overflow-x-hidden bg-background py-12 px-4 font-sans text-foreground transition-colors duration-300">
        <div className="max-w-4xl mx-auto space-y-8 overflow-x-hidden">
          <header className="flex flex-col md:flex-row md:items-start md:justify-between gap-6 mb-12">
            <div className="flex-1 text-center md:text-left">
              <h1 className="text-4xl font-extrabold tracking-tight text-foreground sm:text-5xl mb-4">
                🚗 Admin Dashboard
              </h1>
              <p className="text-lg text-muted-foreground max-w-2xl mx-auto md:mx-0">
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

export default App
