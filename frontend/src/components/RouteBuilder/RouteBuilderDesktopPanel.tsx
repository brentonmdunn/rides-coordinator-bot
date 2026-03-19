/**
 * RouteBuilderDesktopPanel.tsx
 *
 * Collapsible right-side panel shown in the fullscreen overlay on desktop
 * (screen width ≥ 640 px). Contains the show-labels toggle and delegates
 * route-building controls to RouteBuilderPanelContents.
 */

import { ChevronRight, ChevronLeft } from 'lucide-react'
import { RouteBuilderPanelContents } from './RouteBuilderPanelContents'
import type { RouteBuilderPanelContentsProps } from './RouteBuilderPanelContents'

export interface RouteBuilderDesktopPanelProps extends RouteBuilderPanelContentsProps {
    isPanelExpanded: boolean
    onTogglePanelExpanded: () => void
    showLocationLabels: boolean
    onToggleShowLabels: (value: boolean) => void
}

export function RouteBuilderDesktopPanel({
    isPanelExpanded,
    onTogglePanelExpanded,
    showLocationLabels,
    onToggleShowLabels,
    ...panelProps
}: RouteBuilderDesktopPanelProps) {
    return (
        <div
            className={`absolute top-4 right-4 z-[1000] flex transition-all duration-300 ease-in-out ${
                isPanelExpanded ? 'w-80' : 'w-10'
            }`}
        >
            {/* Toggle button that hangs off the left edge of the panel */}
            <button
                onClick={onTogglePanelExpanded}
                className={`absolute -left-3.5 top-1/2 -translate-y-1/2 w-7 h-10 flex items-center justify-center bg-white dark:bg-zinc-800 border border-slate-200 dark:border-zinc-700 rounded-lg shadow-md hover:bg-slate-50 dark:hover:bg-zinc-700 transition-colors z-[1001]
                     ${isPanelExpanded ? '' : 'shadow-lg bg-emerald-50 dark:bg-emerald-900/20 border-emerald-200 dark:border-emerald-800'}`}
                title={isPanelExpanded ? 'Collapse panel' : 'Expand panel'}
            >
                {isPanelExpanded ? (
                    <ChevronRight className="h-4 w-4 text-slate-500 dark:text-slate-400" />
                ) : (
                    <ChevronLeft className="h-4 w-4 text-emerald-600 dark:text-emerald-400" />
                )}
            </button>

            {/* Panel body */}
            <div
                className={`w-full max-h-[calc(100vh-2rem)] overflow-hidden rounded-xl border border-slate-200 dark:border-zinc-700 bg-white/95 dark:bg-zinc-900/95 backdrop-blur-md shadow-xl transition-opacity duration-300 ${
                    isPanelExpanded
                        ? 'opacity-100 pointer-events-auto'
                        : 'opacity-0 pointer-events-none'
                }`}
            >
                <div className="p-4 overflow-y-auto max-h-[calc(100vh-2rem)]">
                    {/* Show labels toggle */}
                    <label className="flex items-center gap-2 mb-3 cursor-pointer select-none">
                        <input
                            type="checkbox"
                            checked={showLocationLabels}
                            onChange={(e) => onToggleShowLabels(e.target.checked)}
                            className="w-4 h-4 rounded accent-emerald-600"
                        />
                        <span className="text-xs font-medium text-slate-600 dark:text-slate-400">
                            Show labels
                        </span>
                    </label>

                    <RouteBuilderPanelContents {...panelProps} />
                </div>
            </div>
        </div>
    )
}
