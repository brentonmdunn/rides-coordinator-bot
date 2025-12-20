import { useState, useEffect } from 'react'
import reactLogo from './assets/react.svg'
import viteLogo from '/vite.svg'
import './App.css'
import { apiFetch } from './lib/api'

function App() {
  const [count, setCount] = useState(0)
  const [apiMessage, setApiMessage] = useState<string>('')
  const [loading, setLoading] = useState(false)

  // Test API connection on mount
  useEffect(() => {
    const testApi = async () => {
      try {
        const response = await apiFetch('/api/hello')
        const data = await response.json()
        setApiMessage(data.message)
      } catch (error) {
        setApiMessage('Failed to connect to API')
        console.error('API Error:', error)
      }
    }
    testApi()
  }, [])

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
      <h1>Vite + React</h1>

      {/* API Status */}
      <div className="card" style={{ marginBottom: '1em' }}>
        <p>API Status: <strong>{apiMessage || 'Connecting...'}</strong></p>
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
