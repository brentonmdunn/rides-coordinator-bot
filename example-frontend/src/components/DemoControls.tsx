import { useState } from 'react'
import { apiFetch } from '../lib/api'
import { Button } from './ui/button'

function DemoControls() {
    const [count, setCount] = useState(0)
    const [loading, setLoading] = useState(false)

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

    return (
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
    )
}

export default DemoControls
