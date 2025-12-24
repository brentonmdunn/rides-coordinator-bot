import './App.css'
import Header from './components/Header'
import PickupLocations from './components/PickupLocations'
import GroupRides from './components/GroupRides'
import DemoControls from './components/DemoControls'
import AskRidesDashboard from './components/AskRidesDashboard/AskRidesDashboard'
import FeatureFlagsManager from './components/FeatureFlagsManager'

function App() {
  return (
    <>
      <Header />
      <PickupLocations />
      <GroupRides />
      <DemoControls />
      <AskRidesDashboard />
      <FeatureFlagsManager />
      <p className="read-the-docs">
        Click on the Vite and React logos to learn more
      </p>
    </>
  )
}

export default App
