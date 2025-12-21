import { useState } from 'react'
import reactLogo from './assets/react.svg'
import viteLogo from '/vite.svg'
import './App.css'
import { apiFetch } from './lib/api'

interface HousingGroup {
  emoji: string
  count: number
  locations: {
    [location: string]: Array<{
      name: string
      discord_username: string | null
    }>
  }
}

interface LocationData {
  housing_groups: {
    [groupName: string]: HousingGroup
  }
  unknown_users: string[]
}

function App() {
  const [count, setCount] = useState(0)
  const [loading, setLoading] = useState(false)

  // Pickup locations form state
  const [messageId, setMessageId] = useState('')
  const [channelId, setChannelId] = useState('939950319721406464')
  const [pickupData, setPickupData] = useState<LocationData | null>(null)
  const [pickupError, setPickupError] = useState<string>('')
  const [pickupLoading, setPickupLoading] = useState(false)

  // Fetch pickups by message ID
  const fetchPickups = async (e: React.FormEvent) => {
    e.preventDefault()
    setPickupLoading(true)
    setPickupError('')
    setPickupData(null)

    try {
      console.log(await apiFetch(
        `/api/locations/pickups-by-message?message_id=${messageId}&channel_id=${channelId}`
      ))
      const response = await apiFetch(
        `/api/locations/pickups-by-message?message_id=${messageId}&channel_id=${channelId}`
      )

      console.log(response)

      // Check response content type
      const contentType = response.headers.get('content-type')
      console.log('Content-Type:', contentType)

      // Get text first to see what we're actually receiving
      const text = await response.text()
      console.log('Response text:', text.substring(0, 200))

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${text}`)
      }

      // Try to parse as JSON
      const data = JSON.parse(text)

      setPickupData(data)
    } catch (error) {
      setPickupError(error instanceof Error ? error.message : 'Unknown error')
      console.error('Pickup fetch error:', error)
    } finally {
      setPickupLoading(false)
    }
  }

  const sendDiscordMessage = async () => {
    setLoading(true)
    try {
      const response = await apiFetch('/api/discord/send-message', {
        method: 'POST'
      })
      const data = await response.json()
      alert(`Success! Message sent by ${data.user_email}`)
    } catch (error) {
      alert('Failed to send Discord message')
      console.error('Discord API Error:', error)
    } finally {
      setLoading(false)
    }
  }

  return (
    <>
      <div>
        <a href="https://vite.dev" target="_blank">
          <img src={viteLogo} className="logo" alt="Vite logo" />
        </a>
        <a href="https://react.dev" target="_blank">
          <img src={reactLogo} className="logo react" alt="React logo" />
        </a>
      </div>
      <h1>Rides Coordinator Admin</h1>

      {/* Pickup Locations Form */}

      <div className="card" style={{ marginBottom: '2em', textAlign: 'left' }}>
        <h2>List Pickups by Message ID</h2>
        <form onSubmit={fetchPickups} style={{ marginBottom: '1em' }}>
          <div style={{ marginBottom: '0.5em' }}>
            <label>
              Message ID:
              <input
                type="text"
                value={messageId}
                onChange={(e) => setMessageId(e.target.value)}
                placeholder="Enter Discord message ID"
                required
                style={{ marginLeft: '0.5em', padding: '0.5em', width: '300px' }}
              />
            </label>
          </div>
          <div style={{ marginBottom: '0.5em' }}>
            <label>
              Channel ID (optional):
              <input
                type="text"
                value={channelId}
                onChange={(e) => setChannelId(e.target.value)}
                placeholder="Enter Discord channel ID"
                style={{ marginLeft: '0.5em', padding: '0.5em', width: '300px' }}
              />
            </label>
          </div>
          <button type="submit" disabled={pickupLoading}>
            {pickupLoading ? 'Loading...' : 'Fetch Pickups'}
          </button>
        </form>

        {/* Error Display */}
        {pickupError && (
          <div style={{ color: 'red', marginBottom: '1em' }}>
            <strong>Error:</strong> {pickupError}
          </div>
        )}

        {/* Raw Data Display */}
        {pickupData && (
          <div style={{ marginTop: '1em' }}>
            <h3>Raw Response:</h3>
            <pre style={{
              background: '#f5f5f5',
              padding: '1em',
              borderRadius: '4px',
              overflow: 'auto',
              maxHeight: '500px',
              textAlign: 'left',
              fontSize: '0.9em'
            }}>
              {JSON.stringify(pickupData, null, 2)}
            </pre>
          </div>
        )}
      </div>

      {/* Demo buttons */}
      <div className="card">
        <button onClick={() => setCount((count) => count + 1)}>
          count is {count}
        </button>

        <button
          onClick={sendDiscordMessage}
          disabled={loading}
          style={{ marginLeft: '1em' }}
        >
          {loading ? 'Sending...' : 'Send Discord Message'}
        </button>

        <p>
          Edit <code>src/App.tsx</code> and save to test HMR
        </p>
      </div>
      <p className="read-the-docs">
        Click on the Vite and React logos to learn more
      </p>
    </>
  )
}

export default App
