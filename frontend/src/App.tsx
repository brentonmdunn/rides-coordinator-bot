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
      {/* <Header /> */}
      <AskRidesDashboard />
      <PickupLocations />
      <GroupRides />
      {/* <DemoControls /> */}
      <FeatureFlagsManager />
    </>
  )
}

export default App
