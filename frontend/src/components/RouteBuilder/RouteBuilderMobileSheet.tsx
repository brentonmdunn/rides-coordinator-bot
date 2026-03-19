/**
 * RouteBuilderMobileSheet.tsx
 *
 * Bottom sheet shown in the fullscreen overlay on mobile (screen width < 640 px).
 * Handles swipe gesture, drag handle, summary header, show-labels toggle, and
 * delegates route-building controls to RouteBuilderPanelContents.
 */

import { useRef } from 'react'
import { ChevronUp, ChevronDown, MapPin } from 'lucide-react'
import { RouteBuilderPanelContents } from './RouteBuilderPanelContents'
import type { RouteBuilderPanelContentsProps } from './RouteBuilderPanelContents'

export interface RouteBuilderMobileSheetProps extends RouteBuilderPanelContentsProps {
    isSheetExpanded: boolean
    onSetSheetExpanded: (expanded: boolean) => void
    showLocationLabels: boolean
    onToggleShowLabels: (value: boolean) => void
}

export function RouteBuilderMobileSheet({
    isSheetExpanded,
    onSetSheetExpanded,
    showLocationLabels,
    onToggleShowLabels,
    selectedLocationKeys,
    ...panelProps
}: RouteBuilderMobileSheetProps) {
    const touchStartYRef = useRef<number | null>(null)
    // Suppress the synthetic click that mobile Safari fires after touchend
    const suppressNextClickRef = useRef(false)

    return (
        <div
            className={`absolute left-0 right-0 bottom-0 z-[1000] bottom-sheet-enter transition-[max-height] duration-300 ease-in-out ${
                isSheetExpanded ? 'max-h-[70vh]' : 'max-h-[4.5rem]'
            }`}
            style={{ willChange: 'max-height' }}
        >
            <div className="bg-white/95 dark:bg-zinc-900/95 backdrop-blur-md border-t border-slate-200 dark:border-zinc-700 rounded-t-2xl shadow-[0_-4px_20px_rgba(0,0,0,0.12)] overflow-hidden h-full flex flex-col">
                {/* Drag handle & summary — always visible */}
                <button
                    onTouchStart={(e) => {
                        touchStartYRef.current = e.touches[0].clientY
                    }}
                    onTouchEnd={(e) => {
                        const startY = touchStartYRef.current
                        if (startY === null) return
                        const deltaY = startY - e.changedTouches[0].clientY
                        touchStartYRef.current = null
                        suppressNextClickRef.current = true
                        // Significant swipe → treat as directional gesture
                        if (Math.abs(deltaY) > 30) {
                            onSetSheetExpanded(deltaY > 0) // swipe up → expand, swipe down → collapse
                        } else {
                            // Small movement = tap → toggle
                            onSetSheetExpanded(!isSheetExpanded)
                        }
                    }}
                    onClick={() => {
                        // Suppress the synthetic click Safari fires after touchend
                        if (suppressNextClickRef.current) {
                            suppressNextClickRef.current = false
                            return
                        }
                        onSetSheetExpanded(!isSheetExpanded)
                    }}
                    className="w-full flex flex-col items-center pt-2.5 pb-2 px-4 active:bg-slate-50 dark:active:bg-zinc-800 transition-colors"
                >
                    <div className="bottom-sheet-handle mb-2" />
                    <div className="flex items-center justify-between w-full">
                        <div className="flex items-center gap-2 text-sm font-semibold text-slate-700 dark:text-slate-300">
                            <MapPin className="h-4 w-4 text-emerald-500" />
                            {selectedLocationKeys.length === 0
                                ? 'Tap pins to add stops'
                                : `${selectedLocationKeys.length} location${selectedLocationKeys.length !== 1 ? 's' : ''} selected`}
                        </div>
                        <div className="flex items-center gap-3">
                            {/* Show labels toggle */}
                            <label
                                className="flex items-center gap-1.5 cursor-pointer select-none"
                                onClick={(e) => e.stopPropagation()}
                            >
                                <input
                                    type="checkbox"
                                    checked={showLocationLabels}
                                    onChange={(e) => onToggleShowLabels(e.target.checked)}
                                    className="w-4 h-4 rounded accent-emerald-600"
                                />
                                <span className="text-xs font-medium text-slate-500 dark:text-slate-400">
                                    Labels
                                </span>
                            </label>
                            {isSheetExpanded ? (
                                <ChevronDown className="h-5 w-5 text-slate-400 dark:text-zinc-500" />
                            ) : (
                                <ChevronUp className="h-5 w-5 text-slate-400 dark:text-zinc-500" />
                            )}
                        </div>
                    </div>
                </button>

                {/* Expanded content */}
                <div
                    className={`overflow-y-auto overscroll-contain px-4 pb-6 transition-opacity duration-200 ${
                        isSheetExpanded ? 'opacity-100' : 'opacity-0 pointer-events-none'
                    }`}
                >
                    <RouteBuilderPanelContents
                        selectedLocationKeys={selectedLocationKeys}
                        {...panelProps}
                    />
                </div>
            </div>
        </div>
    )
}
