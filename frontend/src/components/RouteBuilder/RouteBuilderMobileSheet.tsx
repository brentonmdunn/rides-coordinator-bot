/**
 * RouteBuilderMobileSheet.tsx
 *
 * Bottom sheet shown in the fullscreen overlay on mobile (screen width < 640 px).
 * No swipe gesture — uses explicit tap targets for expand/collapse and a clear button.
 */

import { ChevronUp, ChevronDown, MapPin, X } from 'lucide-react'
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
    return (
        <div
            className={`absolute left-0 right-0 bottom-0 z-[1000] bottom-sheet-enter transition-[max-height] duration-300 ease-in-out ${
                isSheetExpanded ? 'max-h-[70vh]' : 'max-h-[4.5rem]'
            }`}
            style={{ willChange: 'max-height' }}
        >
            <div className="bg-white/95 dark:bg-zinc-900/95 backdrop-blur-md border-t border-slate-200 dark:border-zinc-700 rounded-t-2xl shadow-[0_-4px_20px_rgba(0,0,0,0.12)] overflow-hidden h-full flex flex-col">
                {/* Header bar — entire row is the expand/collapse tap target */}
                <button
                    onClick={() => onSetSheetExpanded(!isSheetExpanded)}
                    aria-label={isSheetExpanded ? 'Collapse panel' : 'Expand panel'}
                    className="flex items-center w-full min-h-[3rem] px-4 bg-slate-50/80 dark:bg-zinc-800/50 active:bg-slate-100 dark:active:bg-zinc-700/60 transition-colors text-left"
                >
                    {/* Location summary */}
                    <MapPin className="h-4 w-4 text-emerald-500 shrink-0 mr-2" />
                    <span className="text-sm font-semibold text-slate-700 dark:text-slate-300 flex-1 truncate">
                        {selectedLocationKeys.length === 0
                            ? 'Tap pins to add stops'
                            : `${selectedLocationKeys.length} location${selectedLocationKeys.length !== 1 ? 's' : ''} selected`}
                    </span>

                    {/* Small controls — stop propagation so they don't toggle the sheet */}
                    <div className="flex items-center gap-3 ml-2 shrink-0" onClick={(e) => e.stopPropagation()}>
                        {/* Show labels toggle */}
                        <label className="flex items-center gap-1.5 cursor-pointer select-none min-h-[44px] px-1">
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

                        {/* Clear button — only when locations are selected */}
                        {selectedLocationKeys.length > 0 && (
                            <button
                                onClick={() => panelProps.onClearAll()}
                                className="flex items-center gap-1.5 text-xs font-medium text-red-500 dark:text-red-400 active:opacity-60 transition-opacity px-3 min-h-[44px] rounded-xl bg-red-50 dark:bg-red-900/20"
                            >
                                <X className="h-3.5 w-3.5" />
                                Clear
                            </button>
                        )}
                    </div>

                    {/* Chevron pill — signals this row is interactive */}
                    <span className="ml-2 shrink-0 flex items-center justify-center w-7 h-7 rounded-full bg-emerald-100 dark:bg-emerald-900/40">
                        {isSheetExpanded ? (
                            <ChevronDown className="h-4 w-4 text-emerald-600 dark:text-emerald-400" />
                        ) : (
                            <ChevronUp className="h-4 w-4 text-emerald-600 dark:text-emerald-400" />
                        )}
                    </span>
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
