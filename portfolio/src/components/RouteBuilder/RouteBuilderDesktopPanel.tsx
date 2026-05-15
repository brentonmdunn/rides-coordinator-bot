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
                className={`absolute -left-3.5 top-1/2 -translate-y-1/2 w-7 h-10 flex items-center justify-center bg-card border border-border rounded-lg shadow-md hover:bg-muted transition-colors z-[1001]
                     ${isPanelExpanded ? '' : 'shadow-lg bg-success/10 border-success/30'}`}
                title={isPanelExpanded ? 'Collapse panel' : 'Expand panel'}
            >
                {isPanelExpanded ? (
                    <ChevronRight className="h-4 w-4 text-muted-foreground" />
                ) : (
                    <ChevronLeft className="h-4 w-4 text-emerald-600 dark:text-emerald-400" />
                )}
            </button>

            {/* Panel body */}
            <div
                className={`w-full max-h-[calc(100vh-2rem)] overflow-hidden rounded-xl border border-border bg-card/95 backdrop-blur-md shadow-xl transition-opacity duration-300 ${
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
                        <span className="text-xs font-medium text-muted-foreground">
                            Show labels
                        </span>
                    </label>

                    <RouteBuilderPanelContents {...panelProps} />
                </div>
            </div>
        </div>
    )
}
