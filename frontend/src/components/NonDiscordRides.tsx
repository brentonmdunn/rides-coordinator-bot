
import { useState, useEffect } from 'react'
import { apiFetch } from '../lib/api'
import { Button } from './ui/button'
import { Input } from './ui/input'
import { Card, CardHeader, CardTitle, CardContent } from './ui/card'
import { InfoToggleButton, InfoPanel } from './InfoHelp'
import ErrorMessage from './ErrorMessage'
import { RefreshCw, Trash2, UserPlus } from 'lucide-react'
import type { NonDiscordRide, NonDiscordRidesListResponse, PickupLocationsResponse } from '../types'

function NonDiscordRides() {
    const [activeDay, setActiveDay] = useState<'Friday' | 'Sunday'>('Friday')
    const [rides, setRides] = useState<NonDiscordRide[]>([])
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState('')
    const [showInfo, setShowInfo] = useState(false)

    // Add form state
    const [newName, setNewName] = useState('')
    const [newLocation, setNewLocation] = useState('')
    const [adding, setAdding] = useState(false)

    // Available locations for autocomplete/select
    const [availableLocations, setAvailableLocations] = useState<string[]>([])

    // Auto-select day based on current time
    useEffect(() => {
        const now = new Date()
        const day = now.getDay()
        const hour = now.getHours()

        if (day === 6 || day === 0 || (day === 5 && hour >= 22)) {
            setActiveDay('Sunday')
        } else {
            setActiveDay('Friday')
        }
    }, [])

    const fetchRides = async () => {
        setLoading(true)
        setError('')
        try {
            const response = await apiFetch(`/api/non-discord-rides/${activeDay.toLowerCase()}`)
            if (!response.ok) throw new Error('Failed to fetch rides')
            const data: NonDiscordRidesListResponse = await response.json()
            setRides(data.rides)
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Unknown error')
        } finally {
            setLoading(false)
        }
    }

    const fetchLocations = async () => {
        try {
            const response = await apiFetch('/api/pickup-locations')
            const data: PickupLocationsResponse = await response.json()
            setAvailableLocations(data.locations.map(l => l.value))
        } catch (error) {
            console.error('Failed to fetch locations', error)
        }
    }

    useEffect(() => {
        fetchRides()
        fetchLocations()
    }, [activeDay])

    const handleAddRide = async (e: React.FormEvent) => {
        e.preventDefault()
        if (!newName || !newLocation) return

        setAdding(true)
        setError('')
        try {
            const response = await apiFetch('/api/non-discord-rides', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    name: newName,
                    day: activeDay,
                    location: newLocation
                })
            })

            if (!response.ok) {
                const result = await response.json()
                throw new Error(result.detail || 'Failed to add ride')
            }

            setNewName('')
            setNewLocation('')
            fetchRides()
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Unknown error')
        } finally {
            setAdding(false)
        }
    }

    const handleRemoveRide = async (name: string) => {
        if (!confirm(`Are you sure you want to remove the ride for ${name}?`)) return

        setLoading(true)
        try {
            const response = await apiFetch(`/api/non-discord-rides?name=${encodeURIComponent(name)}&day=${activeDay}`, {
                method: 'DELETE'
            })

            if (!response.ok) throw new Error('Failed to remove ride')
            fetchRides()
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Unknown error')
            setLoading(false)
        }
    }

    return (
        <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="flex items-center gap-2">
                    <span>📝</span>
                    <span>Non-Discord Rides</span>
                </CardTitle>
                <div className="flex items-center gap-2">
                    <Button
                        variant="ghost"
                        size="sm"
                        onClick={fetchRides}
                        disabled={loading}
                        className="h-8 w-8 p-0"
                    >
                        <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
                    </Button>
                    <InfoToggleButton
                        isOpen={showInfo}
                        onClick={() => setShowInfo(!showInfo)}
                        title="About Non-Discord Rides"
                    />
                </div>
            </CardHeader>
            <CardContent>
                <InfoPanel
                    isOpen={showInfo}
                    onClose={() => setShowInfo(false)}
                    title="About Non-Discord Rides"
                >
                    <p className="mb-2">
                        Manage rides for people who are not in the Discord server.
                    </p>
                    <ul className="list-disc list-inside space-y-1 text-sm text-slate-600 dark:text-slate-400">
                        <li>These rides will be added to the main pickup list.</li>
                        <li>Use this for guests or regular attendees without Discord.</li>
                        <li>Rides are specific to the selected day (Friday/Sunday).</li>
                    </ul>
                </InfoPanel>

                <div className="mb-6 flex gap-2">
                    <Button
                        variant={activeDay === 'Friday' ? 'default' : 'outline'}
                        size="sm"
                        onClick={() => setActiveDay('Friday')}
                        disabled={loading}
                        className="flex-1"
                    >
                        Friday
                    </Button>
                    <Button
                        variant={activeDay === 'Sunday' ? 'default' : 'outline'}
                        size="sm"
                        onClick={() => setActiveDay('Sunday')}
                        disabled={loading}
                        className="flex-1"
                    >
                        Sunday
                    </Button>
                </div>

                <form onSubmit={handleAddRide} className="mb-6 space-y-3 p-4 bg-slate-50 dark:bg-zinc-800/50 rounded-lg border border-slate-100 dark:border-zinc-700">
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                        <div>
                            <label className="text-xs font-medium text-slate-700 dark:text-slate-300 mb-1.5 block">Name</label>
                            <Input
                                value={newName}
                                onChange={(e) => setNewName(e.target.value)}
                                placeholder="Enter name..."
                                required
                            />
                        </div>
                        <div>
                            <label className="text-xs font-medium text-slate-700 dark:text-slate-300 mb-1.5 block">Location</label>
                            <div className="relative">
                                <Input
                                    value={newLocation}
                                    onChange={(e) => setNewLocation(e.target.value)}
                                    placeholder="Enter location..."
                                    required
                                    list="locations-list"
                                />
                                <datalist id="locations-list">
                                    {availableLocations.map(loc => (
                                        <option key={loc} value={loc} />
                                    ))}
                                </datalist>
                            </div>
                        </div>
                    </div>
                    <Button
                        type="submit"
                        disabled={adding || loading}
                        className="w-full"
                        size="sm"
                    >
                        {adding ? 'Adding...' : (
                            <>
                                <UserPlus className="h-4 w-4 mr-2" />
                                Add Ride for {activeDay}
                            </>
                        )}
                    </Button>
                </form>

                <ErrorMessage message={error} />

                <div className="space-y-2">
                    {rides.length === 0 ? (
                        <div className="text-center py-8 text-slate-500 italic">
                            No non-Discord rides found for {activeDay}.
                        </div>
                    ) : (
                        <div className="divide-y divide-slate-100 dark:divide-zinc-800 border border-slate-200 dark:border-zinc-800 rounded-md overflow-hidden">
                            {rides.map((ride) => (
                                <div
                                    key={ride.name}
                                    className="flex items-center justify-between p-3 bg-white dark:bg-zinc-900 group hover:bg-slate-50 dark:hover:bg-zinc-800/50 transition-colors"
                                >
                                    <div>
                                        <div className="font-medium text-slate-900 dark:text-slate-100">{ride.name}</div>
                                        <div className="text-xs text-slate-500 dark:text-slate-400">{ride.location}</div>
                                    </div>
                                    <Button
                                        variant="ghost"
                                        size="icon"
                                        onClick={() => handleRemoveRide(ride.name)}
                                        className="h-8 w-8 text-slate-400 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20"
                                        title="Remove ride"
                                    >
                                        <Trash2 className="h-4 w-4" />
                                    </Button>
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            </CardContent>
        </Card>
    )
}

export default NonDiscordRides
