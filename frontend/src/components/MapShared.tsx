import { useState, useEffect, useCallback } from 'react'
import { useMap } from 'react-leaflet'
import L from 'leaflet'

// Component to recenter map when selected location changes
export function RecenterMap({ center, zoom = 16, bounds }: { center?: [number, number], zoom?: number, bounds?: L.LatLngBoundsExpression }) {
    const map = useMap()

    useEffect(() => {
        if (bounds) {
            map.fitBounds(bounds, { padding: [50, 50], duration: 0.8 })
        } else if (center) {
            map.flyTo(center, zoom, { duration: 0.8 })
        }
    }, [center, zoom, bounds, map])
    return null
}

// Prevents accidental map interaction while scrolling the page.
export function MapInteractionGuard() {
    const map = useMap()
    const [hintMessage, setHintMessage] = useState<string | null>(null)

    const isTouchDevice =
        typeof window !== 'undefined' && 'ontouchstart' in window

    const showHintTemporarily = useCallback(
        (msg: string) => {
            setHintMessage(msg)
            const id = setTimeout(() => setHintMessage(null), 1500)
            return () => clearTimeout(id)
        },
        [setHintMessage]
    )

    // Desktop: gate scroll-zoom behind Cmd/Ctrl, allow free dragging
    useEffect(() => {
        if (isTouchDevice) return

        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const smoothZoom = (map as any).smoothWheelZoom as { enable(): void; disable(): void } | undefined

        const disableZoom = () => {
            map.scrollWheelZoom.disable()
            smoothZoom?.disable()
        }
        const enableZoom = () => {
            map.scrollWheelZoom.enable()
            smoothZoom?.enable()
        }

        disableZoom()
        map.dragging.enable()

        const onKeyDown = (e: KeyboardEvent) => {
            if (e.metaKey || e.ctrlKey) {
                enableZoom()
                setHintMessage(null)
            }
        }
        const onKeyUp = () => {
            disableZoom()
        }
        const onBlur = () => disableZoom()

        window.addEventListener('keydown', onKeyDown)
        window.addEventListener('keyup', onKeyUp)
        window.addEventListener('blur', onBlur)

        return () => {
            window.removeEventListener('keydown', onKeyDown)
            window.removeEventListener('keyup', onKeyUp)
            window.removeEventListener('blur', onBlur)
        }
    }, [map, isTouchDevice])

    // Desktop: show hint on scroll without modifier
    useEffect(() => {
        if (isTouchDevice) return
        const container = map.getContainer()

        const onWheel = (e: WheelEvent) => {
            if (!e.metaKey && !e.ctrlKey) {
                showHintTemporarily('Use ⌘/Ctrl + scroll to zoom')
            }
        }

        container.addEventListener('wheel', onWheel, { passive: true })
        return () => container.removeEventListener('wheel', onWheel)
    }, [map, isTouchDevice, showHintTemporarily])

    // Mobile: require two-finger drag, allow pinch-zoom
    useEffect(() => {
        if (!isTouchDevice) return

        map.dragging.disable()

        const container = map.getContainer()

        const onTouchStart = (e: TouchEvent) => {
            if (e.touches.length >= 2) {
                map.dragging.enable()
            } else {
                map.dragging.disable()
                showHintTemporarily('Use two fingers to move the map')
            }
        }

        const onTouchEnd = () => {
            map.dragging.disable()
        }

        container.addEventListener('touchstart', onTouchStart, {
            passive: true,
        })
        container.addEventListener('touchend', onTouchEnd, { passive: true })
        return () => {
            container.removeEventListener('touchstart', onTouchStart)
            container.removeEventListener('touchend', onTouchEnd)
        }
    }, [map, isTouchDevice, showHintTemporarily])

    return hintMessage ? (
        <div className="absolute inset-0 z-[1000] flex items-center justify-center pointer-events-none">
            <div className="bg-black/70 text-white text-sm px-4 py-2 rounded-lg shadow-lg">
                {hintMessage}
            </div>
        </div>
    ) : null
}
