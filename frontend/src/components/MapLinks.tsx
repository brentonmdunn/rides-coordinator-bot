import { useState, useEffect } from 'react'
import { apiFetch } from '../lib/api'
import { useCopyToClipboard } from '../lib/utils'
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from './ui/select'
import { Card, CardHeader, CardTitle, CardContent } from './ui/card'
import { Copy, Check, ExternalLink } from 'lucide-react'
import { Button } from './ui/button'
import type { PickupLocationsResponse } from '../types'

function MapLinks() {
    const [availableLocations, setAvailableLocations] =
        useState<PickupLocationsResponse | null>(null)
    const [locationsLoading, setLocationsLoading] = useState(true)
    const [selectedLocation, setSelectedLocation] = useState<string>('')
    const { copiedText, copyToClipboard } = useCopyToClipboard(3000)

    useEffect(() => {
        const fetchLocations = async () => {
            try {
                const response = await apiFetch('/api/pickup-locations')
                const data: PickupLocationsResponse = await response.json()
                setAvailableLocations(data)
            } catch (error) {
                console.error('Failed to fetch pickup locations:', error)
            } finally {
                setLocationsLoading(false)
            }
        }

        fetchLocations()
    }, [])

    // Get the display name for the selected location key
    const selectedLocationName =
        availableLocations?.locations.find(
            (loc) => loc.key === selectedLocation
        )?.value ?? ''

    // Get the Google Maps URL for the selected location (map_links uses values as keys)
    const selectedMapUrl = selectedLocationName
        ? (availableLocations?.map_links[selectedLocationName] ?? null)
        : null

    const isCopied = copiedText === selectedMapUrl

    return (
        <Card>
            <CardHeader className="pb-2">
                <CardTitle className="flex items-center gap-2">
                    <span>📍</span>
                    <span>Pickup Directions</span>
                </CardTitle>
            </CardHeader>
            <CardContent>
                <p className="text-sm text-slate-500 dark:text-slate-400 mb-4">
                    Select a pickup location to get its Google Maps link.
                </p>

                {/* Location Dropdown */}
                <div>
                    <Select
                        value={selectedLocation}
                        onValueChange={setSelectedLocation}
                        disabled={locationsLoading}
                    >
                        <SelectTrigger className="w-full">
                            <SelectValue
                                placeholder={
                                    locationsLoading
                                        ? 'Loading locations...'
                                        : 'Choose a location...'
                                }
                            />
                        </SelectTrigger>
                        <SelectContent>
                            {availableLocations?.locations.map((location) => (
                                <SelectItem
                                    key={location.key}
                                    value={location.key}
                                >
                                    {location.value}
                                </SelectItem>
                            ))}
                        </SelectContent>
                    </Select>
                </div>

                {/* Selected Location Details */}
                {selectedMapUrl && (
                    <div className="mt-4 p-4 bg-slate-50 dark:bg-zinc-800/50 rounded-lg border border-slate-100 dark:border-zinc-700 animate-in fade-in slide-in-from-bottom-2 duration-300">
                        <div className="text-sm font-medium text-slate-700 dark:text-slate-300 mb-3">
                            {selectedLocationName}
                        </div>
                        <div className="flex flex-wrap gap-2">
                            <Button
                                type="button"
                                variant="outline"
                                size="sm"
                                onClick={() => copyToClipboard(selectedMapUrl)}
                                className={`transition-all duration-300 ${isCopied
                                        ? 'border-green-500 text-green-600 dark:text-green-400'
                                        : ''
                                    }`}
                            >
                                {isCopied ? (
                                    <>
                                        <Check className="h-4 w-4 mr-1.5" />
                                        Copied!
                                    </>
                                ) : (
                                    <>
                                        <Copy className="h-4 w-4 mr-1.5" />
                                        Copy Link
                                    </>
                                )}
                            </Button>
                            <Button
                                type="button"
                                variant="outline"
                                size="sm"
                                asChild
                            >
                                <a
                                    href={selectedMapUrl}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                >
                                    <ExternalLink className="h-4 w-4 mr-1.5" />
                                    Open in Maps
                                </a>
                            </Button>
                        </div>
                    </div>
                )}
            </CardContent>
        </Card>
    )
}

export default MapLinks
