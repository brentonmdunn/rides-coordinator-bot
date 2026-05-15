import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiFetch } from '../lib/api'
import { Switch } from '@/components/ui/switch'
import { Button } from '@/components/ui/button'
import { InfoToggleButton, InfoPanel } from './InfoHelp'
import ErrorMessage from "./ErrorMessage"
import type { FeatureFlag } from '../types'
import { GridSkeleton } from './LoadingSkeleton'
import { SectionCard } from './shared'

interface FeatureFlagsResponse {
    flags: FeatureFlag[]
}

function FeatureFlagsManager() {
    const queryClient = useQueryClient()
    const [isEditMode, setIsEditMode] = useState(false)
    const [showInfo, setShowInfo] = useState(false)

    // 1. Fetch flags using useQuery
    // ... (unchanged logic)
    const {
        data,
        isLoading: flagsLoading,
        error
    } = useQuery<FeatureFlagsResponse>({
        queryKey: ['featureFlags'],
        queryFn: async () => {
            const response = await apiFetch('/api/feature-flags')
            return response.json()
        }
    })

    const featureFlags = data?.flags || []
    const flagsError = error instanceof Error ? error.message : ''

    // 2. Mutation for toggling flags
    const toggleMutation = useMutation({
        mutationFn: async ({ flagName, enabled }: { flagName: string; enabled: boolean }) => {
            const response = await apiFetch(`/api/feature-flags/${flagName}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ enabled })
            })
            const result = await response.json()
            if (!result.success) {
                throw new Error(result.message || 'Failed to toggle feature flag')
            }
            return result
        },
        onSuccess: () => {
            // Invalidate both feature flags list and rides status
            queryClient.invalidateQueries({ queryKey: ['featureFlags'] })
            queryClient.invalidateQueries({ queryKey: ['askRidesStatus'] })
        },
        onError: (err) => {
            console.error('Feature flag toggle error:', err)
        }
    })

    // Wrapper to match switch signature
    const handleToggle = (flagName: string, enabled: boolean) => {
        toggleMutation.mutate({ flagName, enabled })
    }

    return (
        <SectionCard
            icon="⚙️"
            title="Feature Flags"
            actions={
                <>
                    <Button
                        variant={isEditMode ? "default" : "outline"}
                        size="sm"
                        onClick={() => setIsEditMode(!isEditMode)}
                    >
                        {isEditMode ? "Done" : "Edit"}
                    </Button>
                    <InfoToggleButton
                        isOpen={showInfo}
                        onClick={() => setShowInfo(!showInfo)}
                        title="About Feature Flags"
                    />
                </>
            }
        >
                <InfoPanel
                    isOpen={showInfo}
                    onClose={() => setShowInfo(false)}
                    title="About Feature Flags"
                >
                    <p className="mb-2">
                        Feature flags control global functionality of the bot.
                        Toggling these switches will immediately enable or disable features for all users.
                    </p>
                    <ul className="list-disc list-inside space-y-1">
                        <li><span className="font-medium">Edit Mode</span> is required to make changes.</li>
                        <li>Disabling a flag will stop all associated automated jobs.</li>
                    </ul>
                </InfoPanel>
                {flagsLoading && <GridSkeleton count={6} />}

                <div className="mb-6">
                    <ErrorMessage message={flagsError} />
                </div>

                {toggleMutation.isError && (
                    <div className="mb-4 px-3 py-2 rounded-md bg-destructive/15 border border-destructive/30 text-destructive-text text-sm">
                        Failed to toggle feature flag: {toggleMutation.error instanceof Error ? toggleMutation.error.message : 'Unknown error'}
                    </div>
                )}

                {!flagsLoading && !flagsError && featureFlags.length > 0 && (
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                        {featureFlags.map((flag) => (
                            <div
                                key={flag.id}
                                className="flex items-center justify-between gap-3 rounded-xl border border-border bg-muted/30 px-4 py-3 transition-colors hover:bg-muted/50"
                            >
                                <div className="min-w-0 flex-1">
                                    <p className="text-sm font-medium text-foreground font-mono truncate">
                                        {flag.feature}
                                    </p>
                                    <p className="text-xs text-muted-foreground mt-0.5">
                                        {flag.enabled ? 'Enabled' : 'Disabled'}
                                    </p>
                                </div>
                                <Switch
                                    checked={flag.enabled}
                                    onCheckedChange={(checked) => handleToggle(flag.feature, checked)}
                                    disabled={!isEditMode || toggleMutation.isPending}
                                    aria-label={`Toggle ${flag.feature}`}
                                />
                            </div>
                        ))}
                    </div>
                )}

                {!flagsLoading && !flagsError && featureFlags.length === 0 && (
                    <p className="text-muted-foreground italic p-4 text-center bg-muted/50 rounded-lg">
                        No feature flags found.
                    </p>
                )}
        </SectionCard>
    )
}

export default FeatureFlagsManager
