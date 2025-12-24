import { useState, useEffect } from 'react'
import reactLogo from './assets/react.svg'
import viteLogo from '/vite.svg'
import './App.css'
import { apiFetch } from './lib/api'
import { Switch } from '@/components/ui/switch'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

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

interface FeatureFlag {
  id: number
  feature: string
  enabled: boolean
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

  // Feature flags state
  const [featureFlags, setFeatureFlags] = useState<FeatureFlag[]>([])
  const [flagsLoading, setFlagsLoading] = useState(false)
  const [flagsError, setFlagsError] = useState<string>('')

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

  // Fetch feature flags on component mount
  useEffect(() => {
    fetchFeatureFlags()
  }, [])

  const fetchFeatureFlags = async () => {
    setFlagsLoading(true)
    setFlagsError('')
    try {
      const response = await apiFetch('/api/feature-flags')
      const data = await response.json()
      setFeatureFlags(data.flags)
    } catch (error) {
      setFlagsError(error instanceof Error ? error.message : 'Failed to load feature flags')
      console.error('Feature flags fetch error:', error)
    } finally {
      setFlagsLoading(false)
    }
  }

  const toggleFeatureFlag = async (flagName: string, enabled: boolean) => {
    try {
      const response = await apiFetch(`/api/feature-flags/${flagName}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled })
      })
      const data = await response.json()

      if (data.success) {
        // Update local state
        setFeatureFlags(flags =>
          flags.map(flag =>
            flag.feature === flagName ? { ...flag, enabled } : flag
          )
        )
      } else {
        console.warn(data.message)
      }
    } catch (error) {
      console.error('Feature flag toggle error:', error)
      alert('Failed to toggle feature flag')
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
              <Input
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
              <Input
                type="text"
                value={channelId}
                onChange={(e) => setChannelId(e.target.value)}
                placeholder="Enter Discord channel ID"
              />
            </label>
          </div>
          <Button type="submit" disabled={pickupLoading}>
            {pickupLoading ? 'Loading...' : 'Fetch Pickups'}
          </Button>
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
        <Button onClick={() => setCount((count) => count + 1)}>
          count is {count}
        </Button>

        <Button
          onClick={sendDiscordMessage}
          disabled={loading}
          style={{ marginLeft: '1em' }}
        >
          {loading ? 'Sending...' : 'Send Discord Message'}
        </Button>

        <p>
          Edit <code>src/App.tsx</code> and save to test HMR
        </p>
      </div>

      {/* Feature Flags Management */}
      <div className="card" style={{ marginTop: '2em', textAlign: 'left' }}>
        <h2>⚙️ Feature Flags</h2>

        {flagsLoading && <p>Loading feature flags...</p>}

        {flagsError && (
          <div style={{ color: 'red', marginBottom: '1em' }}>
            <strong>Error:</strong> {flagsError}
          </div>
        )}

        {!flagsLoading && !flagsError && featureFlags.length > 0 && (
          <table style={{ width: '100%', borderCollapse: 'collapse', marginTop: '1em' }}>
            <thead>
              <tr style={{ borderBottom: '2px solid #ccc' }}>
                <th style={{ textAlign: 'left', padding: '0.75em' }}>Feature Flag</th>
                <th style={{ textAlign: 'center', padding: '0.75em', width: '100px' }}>Status</th>
              </tr>
            </thead>
            <tbody>
              {featureFlags.map((flag) => (
                <tr key={flag.id} style={{ borderBottom: '1px solid #eee' }}>
                  <td style={{ padding: '0.75em', fontFamily: 'monospace' }}>
                    {flag.feature}
                  </td>
                  <td style={{ padding: '0.75em', textAlign: 'center' }}>
                    <Switch
                      checked={flag.enabled}
                      onCheckedChange={(checked) => toggleFeatureFlag(flag.feature, checked)}
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        {!flagsLoading && !flagsError && featureFlags.length === 0 && (
          <p style={{ color: '#666', marginTop: '1em' }}>No feature flags found.</p>
        )}
      </div>
      <p className="read-the-docs">
        Click on the Vite and React logos to learn more
      </p>
    </>
  )
}

export default App
