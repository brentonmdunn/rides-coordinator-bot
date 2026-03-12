import { useQuery } from '@tanstack/react-query'
import { MapContainer, TileLayer, Marker, Popup } from 'react-leaflet'
import 'leaflet/dist/leaflet.css'
import { UCSD_CENTER, setupLeafletIcons } from '../components/MapShared'
import { apiFetch } from '../lib/api'
import type { PickupLocationsResponse } from '../types'

// Fix default marker icon
setupLeafletIcons()

export default function RouteBuilder() {
    const { data: locationsData } = useQuery<PickupLocationsResponse>({
        queryKey: ['pickup-locations'],
        queryFn: async () => {
            const res = await apiFetch('/api/pickup-locations')
            return res.json()
        },
    })

    return (
        <div className="h-screen w-full relative">
            <MapContainer
                center={UCSD_CENTER}
                zoom={14}
                style={{ height: '100%', width: '100%' }}
            >
                <TileLayer
                    attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                    url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                />
                
                {locationsData?.locations.map((loc) => {
                    const coords = locationsData.coordinates[loc.value]
                    if (!coords) return null
                    
                    return (
                        <Marker key={loc.key} position={[coords.lat, coords.lng]}>
                            <Popup>{loc.value}</Popup>
                        </Marker>
                    )
                })}
            </MapContainer>
        </div>
    )
}
