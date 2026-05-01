/**
 * RouteBuilder.tsx
 *
 * Slim orchestrator: owns all shared state and handlers, then delegates all
 * rendering to view-specific components:
 *
 *  - RouteBuilderWidget         — the card / widget view (normal page layout)
 *  - RouteBuilderFullscreenMap  — the interactive Leaflet map (fullscreen overlay)
 *  - RouteBuilderDesktopPanel   — collapsible right panel (fullscreen, desktop)
 *  - RouteBuilderMobileSheet    — swipeable bottom sheet (fullscreen, mobile)
 *
 * Builder state (selected stops, time mode, custom time, driver) is mirrored
 * to localStorage and the URL query string so a page refresh or shared link
 * restores the in-progress route.
 */

import { useState, useEffect, useCallback, useRef, useMemo } from 'react'
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

import { PRESET_TIME_MAP, PRESET_TIMES, type TimeModeKey } from './routeBuilderConstants'
import { useRouteGeometry } from './useRouteGeometry'
import { formatDuration, formatTripSummary } from './routeBuilderFormat'

import { RouteBuilderWidget } from './RouteBuilderWidget'
import { RouteBuilderFullscreenMap } from './RouteBuilderFullscreenMap'
import { RouteBuilderDesktopPanel } from './RouteBuilderDesktopPanel'
import { RouteBuilderMobileSheet } from './RouteBuilderMobileSheet'
import { useUsernames } from '../../hooks/useUsernames'

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
// Persistence (localStorage + URL search params)
// ---------------------------------------------------------------------------

const STORAGE_KEY = 'routeBuilder.state.v1'

const URL_KEYS = {
    stops: 'rb_stops',
    timeMode: 'rb_time_mode',
    leaveTime: 'rb_leave_time',
    driver: 'rb_driver',
} as const

const VALID_TIME_MODES: ReadonlySet<TimeModeKey> = new Set(
    PRESET_TIMES.map((p) => p.key)
)

interface PersistedState {
    stops: string[]
    timeMode: TimeModeKey | null
    leaveTime: string | null
    driver: string
}

function loadInitialPersistedState(): PersistedState {
    if (typeof window === 'undefined') {
        return { stops: [], timeMode: null, leaveTime: null, driver: '' }
    }

    let local: Partial<PersistedState> = {}
    try {
        const raw = window.localStorage.getItem(STORAGE_KEY)
        if (raw) local = JSON.parse(raw) as Partial<PersistedState>
    } catch {
        // ignore corrupted localStorage; fall back to defaults
    }

    const url = new URLSearchParams(window.location.search)

    const rawStops = url.get(URL_KEYS.stops)
    const stops = rawStops
        ? rawStops.split(',').map((s) => s.trim()).filter(Boolean)
        : Array.isArray(local.stops)
            ? local.stops
            : []

    const rawTimeMode = url.get(URL_KEYS.timeMode) ?? local.timeMode ?? null
    const timeMode =
        rawTimeMode && VALID_TIME_MODES.has(rawTimeMode as TimeModeKey)
            ? (rawTimeMode as TimeModeKey)
            : null

    const leaveTime = url.get(URL_KEYS.leaveTime) ?? local.leaveTime ?? null
    const driver = url.get(URL_KEYS.driver) ?? local.driver ?? ''

    return { stops, timeMode, leaveTime, driver }
}

function syncPersistedState(state: PersistedState) {
    if (typeof window === 'undefined') return

    try {
        window.localStorage.setItem(STORAGE_KEY, JSON.stringify(state))
    } catch {
        // localStorage may be unavailable (e.g. private mode quota); ignore
    }

    const url = new URL(window.location.href)
    const params = url.searchParams

    if (state.stops.length > 0) {
        params.set(URL_KEYS.stops, state.stops.join(','))
    } else {
        params.delete(URL_KEYS.stops)
    }
    if (state.timeMode) {
        params.set(URL_KEYS.timeMode, state.timeMode)
    } else {
        params.delete(URL_KEYS.timeMode)
    }
    if (state.leaveTime) {
        params.set(URL_KEYS.leaveTime, state.leaveTime)
    } else {
        params.delete(URL_KEYS.leaveTime)
    }
    if (state.driver) {
        params.set(URL_KEYS.driver, state.driver)
    } else {
        params.delete(URL_KEYS.driver)
    }

    const next = `${url.pathname}${params.toString() ? `?${params.toString()}` : ''}${url.hash}`
    window.history.replaceState(window.history.state, '', next)
}

// ---------------------------------------------------------------------------
// Orchestrator
// ---------------------------------------------------------------------------

function RouteBuilder() {
    const { theme } = useTheme()
    const { data: usernames } = useUsernames()
    const isMobile = useIsMobile()

    // --- Hydrate persisted state once on mount ---
    const initialPersisted = useRef<PersistedState>(loadInitialPersistedState())

    // --- Location state ---
    const [selectedLocationKeys, setSelectedLocationKeys] = useState<string[]>(
        initialPersisted.current.stops
    )
    const [lastToggledLocation, setLastToggledLocation] = useState<string | null>(null)

    // --- Panel / sheet state ---
    const [isPanelExpanded, setIsPanelExpanded] = useState(true)
    const [isSheetExpanded, setIsSheetExpanded] = useState(false)

    // --- Time state ---
    const autoMode = getAutomaticDay()
    const initialTimeMode: TimeModeKey = initialPersisted.current.timeMode ?? autoMode
    const initialLeaveTime: string =
        initialPersisted.current.leaveTime ?? PRESET_TIME_MAP[initialTimeMode]
    const [leaveTime, setLeaveTime] = useState(initialLeaveTime)
    const [timeMode, setTimeMode] = useState<TimeModeKey>(initialTimeMode)

    // --- Route state ---
    const [routeOutput, setRouteOutput] = useState<string>('')
    const [originalRouteOutput, setOriginalRouteOutput] = useState<string>('')
    const [routeLoading, setRouteLoading] = useState(false)
    const [routeError, setRouteError] = useState<string>('')
    const { copiedText, copyToClipboard } = useCopyToClipboard(5000)

    // --- Driver state ---
    const [selectedDriver, setSelectedDriver] = useState(initialPersisted.current.driver)
    const driverDay: 'friday' | 'sunday' =
        timeMode === 'sunday' || timeMode === 'sunday_class' ? 'sunday' : 'friday'

    const { data: driverData } = useQuery<{
        reactions: Record<string, string[]>
        username_to_name: Record<string, string>
    }>({
        queryKey: ['driver-reactions', driverDay],
        queryFn: async () => {
            const res = await apiFetch(`/api/check-pickups/driver-reactions/${driverDay}`)
            return res.json()
        },
        staleTime: 5 * 60 * 1000,
    })

    const uniqueDrivers = driverData
        ? [...new Set(Object.values(driverData.reactions).flat())]
        : []

    // Reset driver selection when the day switches (driver lists differ)
    const previousDriverDay = useRef(driverDay)
    useEffect(() => {
        if (previousDriverDay.current !== driverDay) {
            previousDriverDay.current = driverDay
            setSelectedDriver('')
        }
    }, [driverDay])

    // --- User preferences ---
    const queryClient = useQueryClient()

    const { data: prefsData } = useQuery<UserPreferences>({
        queryKey: ['user-preferences'],
        queryFn: async () => {
            const res = await apiFetch('/api/me/preferences')
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

    // Drop persisted stops that no longer exist in the loaded locations list
    // (e.g. a saved key from a previous deploy was removed). Runs once per
    // locations payload, never trims the list to empty if data is still loading.
    const reconciledStaleRef = useRef(false)
    useEffect(() => {
        if (!locationsData || reconciledStaleRef.current) return
        reconciledStaleRef.current = true
        const validKeys = new Set(locationsData.locations.map((l) => l.key))
        setSelectedLocationKeys((prev) => {
            const filtered = prev.filter((k) => validKeys.has(k))
            return filtered.length === prev.length ? prev : filtered
        })
    }, [locationsData])

    // --- Route geometry (shared between widget mini-map and fullscreen map) ---
    const {
        geometry: routeGeometry,
        totalDuration,
        totalDistance,
        legDurations,
    } = useRouteGeometry(selectedLocationKeys, locationsData, getLocationValue)

    const tripSummary = useMemo(
        () => formatTripSummary(totalDuration, totalDistance),
        [totalDuration, totalDistance]
    )

    // legLabels[i] = label for the leg coming into stop i (i ≥ 1).
    // legDurations is length N-1 for N stops, so legLabels[i] = legDurations[i-1].
    const legLabels = useMemo<(string | null)[]>(() => {
        if (selectedLocationKeys.length < 2 || legDurations.length === 0) return []
        return selectedLocationKeys.map((_, i) => {
            if (i === 0) return null
            const dur = formatDuration(legDurations[i - 1] ?? null)
            return dur ? `↓ ${dur}` : null
        })
    }, [selectedLocationKeys, legDurations])

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

    // --- Persist builder state to localStorage + URL ---
    useEffect(() => {
        syncPersistedState({
            stops: selectedLocationKeys,
            timeMode,
            leaveTime,
            driver: selectedDriver,
        })
    }, [selectedLocationKeys, timeMode, leaveTime, selectedDriver])

    // --- Handlers ---

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
            setSelectedDriver('')
            return
        }
        const timer = setTimeout(() => generateRoute(), 300)
        return () => clearTimeout(timer)
    }, [selectedLocationKeys, leaveTime, generateRoute])

    const revertRoute = () => setRouteOutput(originalRouteOutput)

    const routeCopyContent = selectedDriver
        ? `@${selectedDriver} drive: ${routeOutput}`
        : routeOutput

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
        onCopyRoute: () => copyToClipboard(routeCopyContent),
        onRevertRoute: revertRoute,
        copied: copiedText === routeCopyContent,
        drivers: uniqueDrivers,
        driverUsernameToName: driverData?.username_to_name ?? {},
        selectedDriver,
        onSelectDriver: setSelectedDriver,
        tripSummary,
        legLabels,
        usernames,
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
                    aria-label="Exit fullscreen map view"
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
                selectedLocationKeys={selectedLocationKeys}
                getLocationValue={getLocationValue}
                onToggleLocation={toggleLocation}
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
                onCopyRoute={() => copyToClipboard(routeCopyContent)}
                onRevertRoute={revertRoute}
                copied={copiedText === routeCopyContent}
                drivers={uniqueDrivers}
                driverUsernameToName={driverData?.username_to_name ?? {}}
                selectedDriver={selectedDriver}
                onSelectDriver={setSelectedDriver}
                mapBounds={mapBounds}
                routeGeometry={routeGeometry}
                tripSummary={tripSummary}
                legLabels={legLabels}
                lastToggledLocation={lastToggledLocation}
            />

            {fullscreenOverlay}
        </>
    )
}

export default RouteBuilder
