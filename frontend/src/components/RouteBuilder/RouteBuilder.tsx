/**
 * RouteBuilder.tsx
 *
 * Slim orchestrator: owns all shared state and handlers, then delegates all
 * rendering to view-specific components:
 *
 *  - RouteBuilderWidget      — the card / widget view (normal page layout)
 *  - RouteBuilderFullscreenMap  — the interactive Leaflet map (fullscreen overlay)
 *  - RouteBuilderDesktopPanel   — collapsible right panel (fullscreen, desktop)
 *  - RouteBuilderMobileSheet    — swipeable bottom sheet (fullscreen, mobile)
 */

import { useState, useEffect, useCallback, useRef } from 'react'
import { createPortal } from 'react-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft } from 'lucide-react'
import { getAutomaticDay, useCopyToClipboard } from '../../lib/utils'
import { apiFetch } from '../../lib/api'
import { useTheme } from '../use-theme'
import type { PickupLocationsResponse, MakeRouteResponse, UserPreferences } from '../../types'

import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import '@luomus/leaflet-smooth-wheel-zoom'
import { setupLeafletIcons } from '../MapConstants'

import { PRESET_TIME_MAP, type TimeModeKey } from './routeBuilderConstants'
import { useRouteGeometry } from './useRouteGeometry'

import { RouteBuilderWidget } from './RouteBuilderWidget'
import { RouteBuilderFullscreenMap } from './RouteBuilderFullscreenMap'
import { RouteBuilderDesktopPanel } from './RouteBuilderDesktopPanel'
import { RouteBuilderMobileSheet } from './RouteBuilderMobileSheet'

setupLeafletIcons()

// ---------------------------------------------------------------------------
// Lightweight media-query hook
// ---------------------------------------------------------------------------

function useIsMobile(breakpoint = 640) {
    const [isMobile, setIsMobile] = useState(
        typeof window !== 'undefined' ? window.innerWidth < breakpoint : false
    )
    useEffect(() => {
        const mql = window.matchMedia(`(max-width: ${breakpoint - 1}px)`)
        const handler = (e: MediaQueryListEvent) => setIsMobile(e.matches)
        mql.addEventListener('change', handler)
        return () => mql.removeEventListener('change', handler)
    }, [breakpoint])
    return isMobile
}

// ---------------------------------------------------------------------------
// Orchestrator
// ---------------------------------------------------------------------------

function RouteBuilder() {
    const { theme } = useTheme()
    const isMobile = useIsMobile()

    // --- Location state ---
    const [selectedLocation, setSelectedLocation] = useState<string>('')
    const [selectedLocationKeys, setSelectedLocationKeys] = useState<string[]>([])
    const [lastToggledLocation, setLastToggledLocation] = useState<string | null>(null)

    // --- Panel / sheet state ---
    const [isPanelExpanded, setIsPanelExpanded] = useState(true)
    const [isSheetExpanded, setIsSheetExpanded] = useState(false)

    // --- Time state ---
    const autoMode = getAutomaticDay()
    const [leaveTime, setLeaveTime] = useState(PRESET_TIME_MAP[autoMode])
    const [timeMode, setTimeMode] = useState<TimeModeKey>(autoMode)

    // --- Route state ---
    const [routeOutput, setRouteOutput] = useState<string>('')
    const [originalRouteOutput, setOriginalRouteOutput] = useState<string>('')
    const [routeLoading, setRouteLoading] = useState(false)
    const [routeError, setRouteError] = useState<string>('')
    const { copiedText, copyToClipboard } = useCopyToClipboard(5000)

    // --- User preferences ---
    const queryClient = useQueryClient()

    const { data: prefsData } = useQuery<UserPreferences>({
        queryKey: ['user-preferences'],
        queryFn: async () => {
            const res = await apiFetch('/api/me/preferences')
            if (!res.ok) throw new Error('Failed to load preferences')
            return res.json()
        },
        staleTime: Infinity,
    })

    const [showLocationLabels, setShowLocationLabels] = useState(true)

    useEffect(() => {
        if (prefsData !== undefined) {
            setShowLocationLabels(prefsData.show_map_labels)
        }
    }, [prefsData])

    const prefsMutation = useMutation({
        mutationFn: async (value: boolean) => {
            const res = await apiFetch('/api/me/preferences', {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ show_map_labels: value }),
            })
            if (!res.ok) throw new Error('Failed to save preference')
            return res.json() as Promise<UserPreferences>
        },
        onSuccess: (data) => {
            queryClient.setQueryData(['user-preferences'], data)
        },
    })

    const toggleShowLabels = (value: boolean) => {
        setShowLocationLabels(value)
        prefsMutation.mutate(value)
    }

    // --- Mini-map bounds (widget mode) ---
    const [mapBounds, setMapBounds] = useState<L.LatLngBoundsExpression | undefined>(undefined)

    // --- Info panel ---
    const [showInfo, setShowInfo] = useState(false)

    // --- Fullscreen transition: two-phase mount/animate pattern ---
    const [isFullscreenMounted, setIsFullscreenMounted] = useState(false)
    const [isFullscreenVisible, setIsFullscreenVisible] = useState(false)
    const fullscreenTransitionRef = useRef<number | null>(null)

    const openFullscreen = useCallback(() => {
        setIsFullscreenMounted(true)
        fullscreenTransitionRef.current = requestAnimationFrame(() => {
            fullscreenTransitionRef.current = requestAnimationFrame(() => {
                setIsFullscreenVisible(true)
            })
        })
    }, [])

    const closeFullscreen = useCallback(() => {
        setIsFullscreenVisible(false)
    }, [])

    useEffect(() => {
        return () => {
            if (fullscreenTransitionRef.current !== null) {
                cancelAnimationFrame(fullscreenTransitionRef.current)
            }
        }
    }, [])

    // --- Fetch pickup locations ---
    const { data: locationsData, isLoading: locationsLoading } = useQuery<PickupLocationsResponse>({
        queryKey: ['pickup-locations'],
        queryFn: async () => {
            const res = await apiFetch('/api/pickup-locations')
            return res.json()
        },
    })

    const getLocationValue = useCallback(
        (key: string): string => {
            return locationsData?.locations.find((loc) => loc.key === key)?.value || key
        },
        [locationsData]
    )

    // --- Route geometry (shared between widget mini-map and fullscreen map) ---
    const routeGeometry = useRouteGeometry(selectedLocationKeys, locationsData, getLocationValue)

    // --- Update mini-map bounds when selected locations change ---
    useEffect(() => {
        if (!locationsData) return

        if (selectedLocationKeys.length === 0) {
            setMapBounds(undefined)
            return
        }

        if (selectedLocationKeys.length === 1) {
            const name = getLocationValue(selectedLocationKeys[0])
            const singleCoord = locationsData.coordinates[name]
            if (singleCoord) {
                setMapBounds([
                    [singleCoord.lat - 0.01, singleCoord.lng - 0.01],
                    [singleCoord.lat + 0.01, singleCoord.lng + 0.01],
                ])
            }
            return
        }

        const coords = selectedLocationKeys
            .map((key) => locationsData.coordinates[getLocationValue(key)])
            .filter(Boolean)

        if (coords.length < 2) return

        const lats = coords.map((c) => c.lat)
        const lngs = coords.map((c) => c.lng)
        const latPadding = (Math.max(...lats) - Math.min(...lats)) * 0.1 || 0.01
        const lngPadding = (Math.max(...lngs) - Math.min(...lngs)) * 0.1 || 0.01

        setMapBounds([
            [Math.min(...lats) - latPadding, Math.min(...lngs) - lngPadding],
            [Math.max(...lats) + latPadding, Math.max(...lngs) + lngPadding],
        ])
    }, [selectedLocationKeys, locationsData, getLocationValue])

    // Close fullscreen on Escape key
    useEffect(() => {
        if (!isFullscreenMounted) return
        const onKeyDown = (e: KeyboardEvent) => {
            if (e.key === 'Escape') closeFullscreen()
        }
        window.addEventListener('keydown', onKeyDown)
        return () => window.removeEventListener('keydown', onKeyDown)
    }, [isFullscreenMounted, closeFullscreen])

    // Prevent body scroll when fullscreen overlay is open
    useEffect(() => {
        document.body.style.overflow = isFullscreenMounted ? 'hidden' : ''
        return () => {
            document.body.style.overflow = ''
        }
    }, [isFullscreenMounted])

    // --- Handlers ---

    const addLocation = () => {
        if (selectedLocation && !selectedLocationKeys.includes(selectedLocation)) {
            setSelectedLocationKeys([...selectedLocationKeys, selectedLocation])
            setSelectedLocation('')
        }
    }

    const toggleLocation = (key: string) => {
        setLastToggledLocation(key)
        setSelectedLocationKeys((prev) =>
            prev.includes(key) ? prev.filter((k) => k !== key) : [...prev, key]
        )
        // Clear after the 0.35s bounce animation so any unrelated re-render
        // (e.g. changing the preset time) doesn't replay the animation.
        setTimeout(() => setLastToggledLocation(null), 400)
    }

    const generateRoute = useCallback(async () => {
        setRouteLoading(true)
        setRouteError('')
        setRouteOutput('')
        setOriginalRouteOutput('')
        try {
            const response = await apiFetch('/api/make-route', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    locations: selectedLocationKeys,
                    leave_time: leaveTime,
                }),
            })
            const result: MakeRouteResponse = await response.json()
            if (result.success && result.route) {
                setRouteOutput(result.route)
                setOriginalRouteOutput(result.route)
            } else {
                setRouteError(result.error || 'Failed to generate route')
            }
        } catch (error) {
            setRouteError(error instanceof Error ? error.message : 'Unknown error')
            console.error('Route generation error:', error)
        } finally {
            setRouteLoading(false)
        }
    }, [selectedLocationKeys, leaveTime])

    // Auto-generate route whenever locations or leave time change
    useEffect(() => {
        if (selectedLocationKeys.length === 0 || !leaveTime) {
            setRouteOutput('')
            setOriginalRouteOutput('')
            setRouteError('')
            return
        }
        const timer = setTimeout(() => generateRoute(), 300)
        return () => clearTimeout(timer)
    }, [selectedLocationKeys, leaveTime, generateRoute])

    const revertRoute = () => setRouteOutput(originalRouteOutput)

    // --- Shared panel props (forwarded to both desktop panel and mobile sheet) ---
    const panelProps = {
        selectedLocationKeys,
        getLocationValue,
        onRemoveLocation: (index: number) =>
            setSelectedLocationKeys((prev) => prev.filter((_, i) => i !== index)),
        onReorderLocations: setSelectedLocationKeys,
        onClearAll: () => setSelectedLocationKeys([]),
        timeMode,
        leaveTime,
        onTimeModeChange: (mode: TimeModeKey, time: string) => {
            setTimeMode(mode)
            setLeaveTime(time)
        },
        onLeaveTimeChange: setLeaveTime,
        routeLoading,
        routeError,
        routeOutput,
        originalRouteOutput,
        onChangeRouteOutput: setRouteOutput,
        onCopyRoute: () => copyToClipboard(routeOutput),
        onRevertRoute: revertRoute,
        copied: copiedText === routeOutput,
    }

    // --- Fullscreen overlay (rendered via portal) ---
    const fullscreenOverlay = isFullscreenMounted
        ? createPortal(
            <div
                className={`fixed inset-0 z-50 bg-white dark:bg-zinc-950 overflow-hidden transition-all duration-300 ease-out ${isFullscreenVisible ? 'opacity-100 scale-100' : 'opacity-0 scale-[0.97]'
                    }`}
                onTransitionEnd={(e) => {
                    if (e.propertyName === 'opacity' && !isFullscreenVisible) {
                        setIsFullscreenMounted(false)
                        setIsSheetExpanded(false)
                    }
                }}
            >
                {/* Full-screen interactive map */}
                <RouteBuilderFullscreenMap
                    theme={theme}
                    locationsData={locationsData}
                    selectedLocationKeys={selectedLocationKeys}
                    lastToggledLocation={lastToggledLocation}
                    showLocationLabels={showLocationLabels}
                    routeGeometry={routeGeometry}
                    onToggleLocation={toggleLocation}
                />

                {/* Back button (top-left, near zoom controls) */}
                <button
                    onClick={closeFullscreen}
                    className="absolute top-24 left-4 z-[1000] flex items-center gap-2 px-3 py-2 bg-white/95 dark:bg-zinc-900/95 backdrop-blur-sm border border-slate-200 dark:border-zinc-700 rounded-lg shadow-[0_4px_12px_rgba(0,0,0,0.1)] hover:bg-slate-50 dark:hover:bg-zinc-800 transition-colors text-slate-700 dark:text-slate-300"
                    title="Exit fullscreen (Esc)"
                >
                    <ArrowLeft className="h-4 w-4" />
                    <span className="text-sm font-semibold">Back</span>
                    {!isMobile && (
                        <span className="text-[10px] font-bold tracking-wider text-slate-400 dark:text-zinc-500 bg-slate-100 dark:bg-zinc-800 px-1.5 py-0.5 rounded ml-1">
                            ESC
                        </span>
                    )}
                </button>

                {/* Desktop: right side panel */}
                {!isMobile && (
                    <RouteBuilderDesktopPanel
                        {...panelProps}
                        isPanelExpanded={isPanelExpanded}
                        onTogglePanelExpanded={() => setIsPanelExpanded((v) => !v)}
                        showLocationLabels={showLocationLabels}
                        onToggleShowLabels={toggleShowLabels}
                    />
                )}

                {/* Mobile: bottom sheet */}
                {isMobile && (
                    <RouteBuilderMobileSheet
                        {...panelProps}
                        isSheetExpanded={isSheetExpanded}
                        onSetSheetExpanded={setIsSheetExpanded}
                        showLocationLabels={showLocationLabels}
                        onToggleShowLabels={toggleShowLabels}
                    />
                )}
            </div>,
            document.body
        )
        : null

    // --- Widget card view ---
    return (
        <>
            <RouteBuilderWidget
                theme={theme}
                showInfo={showInfo}
                onToggleInfo={() => setShowInfo((v) => !v)}
                onOpenFullscreen={openFullscreen}
                locationsData={locationsData}
                locationsLoading={locationsLoading}
                selectedLocation={selectedLocation}
                onSelectLocation={setSelectedLocation}
                selectedLocationKeys={selectedLocationKeys}
                getLocationValue={getLocationValue}
                onAddLocation={addLocation}
                onRemoveLocation={(index) =>
                    setSelectedLocationKeys((prev) => prev.filter((_, i) => i !== index))
                }
                onReorderLocations={setSelectedLocationKeys}
                timeMode={timeMode}
                leaveTime={leaveTime}
                onTimeModeChange={(mode, time) => {
                    setTimeMode(mode)
                    setLeaveTime(time)
                }}
                onLeaveTimeChange={setLeaveTime}
                routeLoading={routeLoading}
                routeError={routeError}
                routeOutput={routeOutput}
                originalRouteOutput={originalRouteOutput}
                onChangeRouteOutput={setRouteOutput}
                onCopyRoute={() => copyToClipboard(routeOutput)}
                onRevertRoute={revertRoute}
                copied={copiedText === routeOutput}
                mapBounds={mapBounds}
                routeGeometry={routeGeometry}
            />

            {fullscreenOverlay}
        </>
    )
}

export default RouteBuilder
