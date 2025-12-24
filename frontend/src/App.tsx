import { useState, useEffect } from 'react'
import reactLogo from './assets/react.svg'
import viteLogo from '/vite.svg'
import './App.css'
import { apiFetch } from './lib/api'
import { Switch } from '@/components/ui/switch'
import { Button } from './components/ui/button'
import { Input } from './components/ui/input'
import RideTypeSelector, { type RideType } from './components/RideTypeSelector'
import ErrorMessage from "./components/ErrorMessage"

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

interface AskRidesJobStatus {
  enabled: boolean
  will_send: boolean
  reason: string | null
  next_run: string
  last_message?: {
    message_id: string
    reactions: { [emoji: string]: number }
  } | null
}

interface AskRidesStatus {
  friday: AskRidesJobStatus
  sunday: AskRidesJobStatus
  sunday_class: AskRidesJobStatus
}

interface GroupRidesResponse {
  success: boolean
  summary: string | null
  groupings: string[] | null
  error: string | null
}

function App() {
  const [count, setCount] = useState(0)
  const [loading, setLoading] = useState(false)

  // Pickup locations form state
  const [pickupRideType, setPickupRideType] = useState<RideType>('friday')
  const [messageId, setMessageId] = useState('')
  const [channelId, setChannelId] = useState('939950319721406464')
  const [pickupData, setPickupData] = useState<LocationData | null>(null)
  const [pickupError, setPickupError] = useState<string>('')
  const [pickupLoading, setPickupLoading] = useState(false)

  // Feature flags state
  const [featureFlags, setFeatureFlags] = useState<FeatureFlag[]>([])
  const [flagsLoading, setFlagsLoading] = useState(false)
  const [flagsError, setFlagsError] = useState<string>('')

  // Ask Rides status state
  const [askRidesStatus, setAskRidesStatus] = useState<AskRidesStatus | null>(null)
  const [askRidesLoading, setAskRidesLoading] = useState(false)
  const [askRidesError, setAskRidesError] = useState<string>('')

  // Group Rides state
  const [rideType, setRideType] = useState<RideType>('friday')
  const [groupMessageId, setGroupMessageId] = useState('')
  const [groupDriverCapacity, setGroupDriverCapacity] = useState('44444')
  const [groupRidesSummary, setGroupRidesSummary] = useState<string | null>(null)
  const [groupRidesData, setGroupRidesData] = useState<string[] | null>(null)
  const [groupRidesError, setGroupRidesError] = useState<string>('')
  const [groupRidesLoading, setGroupRidesLoading] = useState(false)
  const [copiedIndex, setCopiedIndex] = useState<number | null>(null)

  // Fetch pickups by message ID
  const fetchPickups = async (e: React.FormEvent) => {
    e.preventDefault()
    setPickupLoading(true)
    setPickupError('')
    setPickupData(null)

    try {
      const response = await apiFetch('/api/list-pickups', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ride_type: pickupRideType,
          message_id: pickupRideType === 'message_id' ? messageId : null,
          channel_id: channelId
        })
      })

      const result = await response.json()

      if (result.success && result.data) {
        setPickupData(result.data)
      } else {
        setPickupError(result.error || 'Failed to fetch pickups')
      }
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
      alert(`Success! Message sent by ${data.user_email} `)
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

  // Fetch ask rides status on component mount
  useEffect(() => {
    fetchAskRidesStatus()
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
        // Refresh ask rides status since feature flags changed
        fetchAskRidesStatus()
      } else {
        console.warn(data.message)
      }
    } catch (error) {
      console.error('Feature flag toggle error:', error)
      alert('Failed to toggle feature flag')
    }
  }

  const fetchAskRidesStatus = async () => {
    setAskRidesLoading(true)
    setAskRidesError('')
    try {
      const response = await apiFetch('/api/ask-rides/status')
      const data = await response.json()
      setAskRidesStatus(data)
    } catch (error) {
      setAskRidesError(error instanceof Error ? error.message : 'Failed to load ask rides status')
      console.error('Ask rides status fetch error:', error)
    } finally {
      setAskRidesLoading(false)
    }
  }

  const formatDateTime = (isoString: string): string => {
    const date = new Date(isoString)
    return date.toLocaleString('en-US', {
      weekday: 'short',
      month: 'short',
      day: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
      hour12: true
    })
  }

  const getStatusBadge = (job: AskRidesJobStatus) => {
    if (!job.enabled) {
      return { color: '#ef4444', text: '🔴 Feature flag disabled' }
    }
    if (!job.will_send) {
      const reasonText = job.reason === 'wildcard_detected'
        ? 'Wildcard event detected'
        : 'No class scheduled'
      return { color: '#eab308', text: `🟡 Will not send - ${reasonText} ` }
    }
    return { color: '#22c55e', text: `🟢 Will send at ${formatDateTime(job.next_run)} ` }
  }

  const groupRides = async (e: React.FormEvent) => {
    e.preventDefault()
    setGroupRidesLoading(true)
    setGroupRidesError('')
    setGroupRidesSummary(null)
    setGroupRidesData(null)

    try {
      const response = await apiFetch('/api/group-rides', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ride_type: rideType,
          message_id: rideType === 'message_id' ? groupMessageId : null,
          driver_capacity: groupDriverCapacity,
          channel_id: channelId
        })
      })

      const data: GroupRidesResponse = await response.json()

      if (data.success && data.groupings) {
        setGroupRidesSummary(data.summary)
        setGroupRidesData(data.groupings)
      } else {
        setGroupRidesError(data.error || 'Failed to group rides')
      }
    } catch (error) {
      setGroupRidesError(error instanceof Error ? error.message : 'Unknown error')
      console.error('Group rides error:', error)
    } finally {
      setGroupRidesLoading(false)
    }
  }

  const copyToClipboard = async (text: string, index: number) => {
    try {
      await navigator.clipboard.writeText(text)
      setCopiedIndex(index)
      // Reset after 5 seconds
      setTimeout(() => setCopiedIndex(null), 5000)
    } catch (error) {
      console.error('Failed to copy:', error)
      alert('Failed to copy to clipboard')
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
        <h2>📍 List Pickups</h2>
        <form onSubmit={fetchPickups} style={{ marginBottom: '1em' }}>
          {/* Ride Type Selection */}
          <RideTypeSelector value={pickupRideType} onChange={setPickupRideType} />

          {/* Message ID Input (only shown when message_id is selected) */}
          {pickupRideType === 'message_id' && (
            <div style={{ marginBottom: '1em', padding: '1em', background: '#f9fafb', borderRadius: '8px' }}>
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
          )}

          <Button type="submit" disabled={pickupLoading} style={{
            padding: '0.75em 1.5em',
            fontSize: '1em',
            fontWeight: 'bold'
          }}>
            {pickupLoading ? 'Loading...' : 'Fetch Pickups'}
          </Button>
        </form>

        {/* Error Display */}
        <ErrorMessage message={pickupError} />

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

      {/* Group Rides Form */}
      <div className="card" style={{ marginBottom: '2em', textAlign: 'left' }}>
        <h2>🚗 Group Rides</h2>
        <form onSubmit={groupRides} style={{ marginBottom: '1em' }}>
          {/* Ride Type Selection */}
          <RideTypeSelector value={rideType} onChange={setRideType} />

          {/* Message ID Input (only shown when message_id is selected) */}
          {rideType === 'message_id' && (
            <div style={{ marginBottom: '1em', padding: '1em', background: '#f9fafb', borderRadius: '8px' }}>
              <label>
                Message ID:
                <Input
                  type="text"
                  value={groupMessageId}
                  onChange={(e) => setGroupMessageId(e.target.value)}
                  placeholder="Enter Discord message ID"
                  required
                  style={{ marginLeft: '0.5em', padding: '0.5em', width: '300px' }}
                />
              </label>
            </div>
          )}

          {/* Driver Capacity */}
          <div style={{ marginBottom: '1.5em' }}>
            <label>
              Driver Capacity:
              <Input
                type="text"
                value={groupDriverCapacity}
                onChange={(e) => setGroupDriverCapacity(e.target.value)}
                placeholder="e.g., 44444"
                style={{ marginLeft: '0.5em', padding: '0.5em', width: '150px' }}
              />
              <span style={{ marginLeft: '0.5em', fontSize: '0.9em', color: '#6b7280' }}>
                (One digit per driver, e.g., "44444" = 5 drivers with 4 seats each)
              </span>
            </label>
          </div>

          <Button type="submit" disabled={groupRidesLoading} style={{
            padding: '0.75em 1.5em',
            fontSize: '1em',
            fontWeight: 'bold'
          }}>
            {groupRidesLoading ? 'Grouping Rides...' : 'Group Rides'}
          </Button>
        </form>

        {/* Loading Indicator */}
        {groupRidesLoading && (
          <div style={{
            padding: '1em',
            background: '#e3f2fd',
            borderRadius: '4px',
            marginBottom: '1em',
            color: '#1976d2'
          }}>
            <strong>⏳ Grouping rides...</strong>
            <p style={{ margin: '0.5em 0 0 0', fontSize: '0.9em' }}>
              This may take 15-30 seconds. Please wait...
            </p>
          </div>
        )}

        {/* Error Display */}
        <ErrorMessage message={groupRidesError} />

        {/* Results Display */}
        {(groupRidesSummary || groupRidesData) && (
          <div style={{ marginTop: '1em' }}>
            {/* Summary Section */}
            {groupRidesSummary && (
              <div style={{ marginBottom: '1.5em' }}>
                <h3>Summary:</h3>
                <pre style={{
                  whiteSpace: 'pre-wrap',
                  wordWrap: 'break-word',
                  padding: '1em',
                  background: '#e8f5e9',
                  borderRadius: '4px',
                  fontSize: '0.9em',
                  fontFamily: 'monospace',
                  border: '1px solid #4caf50'
                }}>
                  {groupRidesSummary}
                </pre>
              </div>
            )}

            {/* Individual Ride Groupings */}
            {groupRidesData && (
              <>
                <h3>Ride Groupings:</h3>
                {groupRidesData.map((grouping, index) => (
                  <div
                    key={index}
                    style={{
                      marginBottom: '1em',
                      padding: '1em',
                      background: '#f5f5f5',
                      borderRadius: '4px',
                      position: 'relative'
                    }}
                  >
                    <Button
                      onClick={() => copyToClipboard(grouping, index)}
                      style={{
                        position: 'absolute',
                        top: '0.5em',
                        right: '0.5em',
                        padding: '0.25em 0.5em',
                        fontSize: '0.85em'
                      }}
                    >
                      {copiedIndex === index ? '✓ Copied!' : '📋 Copy'}
                    </Button>
                    <pre style={{
                      whiteSpace: 'pre-wrap',
                      wordWrap: 'break-word',
                      margin: 0,
                      paddingRight: '5em',
                      fontSize: '0.9em',
                      fontFamily: 'monospace'
                    }}>
                      {grouping}
                    </pre>
                  </div>
                ))}
              </>
            )}
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

      {/* Ask Rides Status Dashboard */}
      <div className="card" style={{ marginTop: '2em', textAlign: 'left' }}>
        <h2>📅 Ask Rides Status Dashboard</h2>

        {askRidesLoading && <p>Loading ask rides status...</p>}

        <ErrorMessage message={askRidesError} />

        {!askRidesLoading && !askRidesError && askRidesStatus && (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '1em', marginTop: '1em' }}>
            {/* Friday Fellowship */}
            <div style={{
              border: '1px solid #ddd',
              borderRadius: '8px',
              padding: '1em',
              background: '#f9f9f9'
            }}>
              <h3 style={{ marginTop: 0, marginBottom: '0.5em' }}>🎉 Friday Fellowship</h3>
              <div style={{
                padding: '0.5em',
                borderRadius: '4px',
                background: getStatusBadge(askRidesStatus.friday).color + '22',
                color: getStatusBadge(askRidesStatus.friday).color,
                fontWeight: 'bold',
                marginBottom: '0.5em'
              }}>
                {getStatusBadge(askRidesStatus.friday).text}
              </div>
              {askRidesStatus.friday.last_message && (
                <div style={{ marginTop: '0.5em', fontSize: '0.9em' }}>
                  <strong>Last message reactions:</strong>
                  <div style={{ marginTop: '0.25em' }}>
                    {Object.entries(askRidesStatus.friday.last_message.reactions).map(([emoji, count]) => (
                      <span key={emoji} style={{ marginRight: '0.75em' }}>
                        {emoji} {count}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Sunday Service */}
            <div style={{
              border: '1px solid #ddd',
              borderRadius: '8px',
              padding: '1em',
              background: '#f9f9f9'
            }}>
              <h3 style={{ marginTop: 0, marginBottom: '0.5em' }}>⛪ Sunday Service</h3>
              <div style={{
                padding: '0.5em',
                borderRadius: '4px',
                background: getStatusBadge(askRidesStatus.sunday).color + '22',
                color: getStatusBadge(askRidesStatus.sunday).color,
                fontWeight: 'bold',
                marginBottom: '0.5em'
              }}>
                {getStatusBadge(askRidesStatus.sunday).text}
              </div>
              {askRidesStatus.sunday.last_message && (
                <div style={{ marginTop: '0.5em', fontSize: '0.9em' }}>
                  <strong>Last message reactions:</strong>
                  <div style={{ marginTop: '0.25em' }}>
                    {Object.entries(askRidesStatus.sunday.last_message.reactions).map(([emoji, count]) => (
                      <span key={emoji} style={{ marginRight: '0.75em' }}>
                        {emoji} {count}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Sunday Class */}
            <div style={{
              border: '1px solid #ddd',
              borderRadius: '8px',
              padding: '1em',
              background: '#f9f9f9'
            }}>
              <h3 style={{ marginTop: 0, marginBottom: '0.5em' }}>📖 Sunday Class</h3>
              <div style={{
                padding: '0.5em',
                borderRadius: '4px',
                background: getStatusBadge(askRidesStatus.sunday_class).color + '22',
                color: getStatusBadge(askRidesStatus.sunday_class).color,
                fontWeight: 'bold',
                marginBottom: '0.5em'
              }}>
                {getStatusBadge(askRidesStatus.sunday_class).text}
              </div>
              {askRidesStatus.sunday_class.last_message && (
                <div style={{ marginTop: '0.5em', fontSize: '0.9em' }}>
                  <strong>Last message reactions:</strong>
                  <div style={{ marginTop: '0.25em' }}>
                    {Object.entries(askRidesStatus.sunday_class.last_message.reactions).map(([emoji, count]) => (
                      <span key={emoji} style={{ marginRight: '0.75em' }}>
                        {emoji} {count}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Feature Flags Management */}
      <div className="card" style={{ marginTop: '2em', textAlign: 'left' }}>
        <h2>⚙️ Feature Flags</h2>

        {flagsLoading && <p>Loading feature flags...</p>}

        <ErrorMessage message={flagsError} />

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
