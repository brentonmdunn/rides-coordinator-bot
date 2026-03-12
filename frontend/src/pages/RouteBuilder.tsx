import { MapContainer, TileLayer } from 'react-leaflet'
import 'leaflet/dist/leaflet.css'
import { UCSD_CENTER, setupLeafletIcons } from '../components/MapShared'

// Fix default marker icon
setupLeafletIcons()

export default function RouteBuilder() {
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
            </MapContainer>
        </div>
    )
}
