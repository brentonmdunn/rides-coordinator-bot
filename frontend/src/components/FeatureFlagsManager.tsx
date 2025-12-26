import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiFetch } from '../lib/api'
import { Switch } from '@/components/ui/switch'
import { Button } from '@/components/ui/button'
import { InfoToggleButton, InfoPanel } from './InfoHelp'
import ErrorMessage from "./ErrorMessage"
import type { FeatureFlag } from '../types'

interface FeatureFlagsResponse {
    flags: FeatureFlag[]
}

import { Card, CardHeader, CardTitle, CardContent } from './ui/card'

// ... existing imports

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
            if (!response.ok) {
                throw new Error('Failed to load feature flags')
            }
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
            alert('Failed to toggle feature flag')
        }
    })

    // Wrapper to match switch signature
    const handleToggle = (flagName: string, enabled: boolean) => {
        toggleMutation.mutate({ flagName, enabled })
    }

    return (
        <Card>
            <CardHeader>
                <div className="flex items-center justify-between">
                    <CardTitle className="flex items-center gap-2">
                        <span>⚙️</span>
                        <span>Feature Flags</span>
                    </CardTitle>
                    <div className="flex items-center gap-2">
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

                    </div>
                </div>
            </CardHeader>
            <CardContent>
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
                {flagsLoading && (
                    <div className="p-8 text-center text-slate-500 animate-pulse">
                        Loading feature flags...
                    </div>
                )}

                <div className="mb-6">
                    <ErrorMessage message={flagsError} />
                </div>

                {!flagsLoading && !flagsError && featureFlags.length > 0 && (
                    <div className="rounded-lg border border-slate-200 dark:border-zinc-800 overflow-x-auto">
                        <table className="w-full text-left text-sm">
                            <thead className="bg-slate-50 dark:bg-zinc-800/50 text-slate-900 dark:text-slate-100 font-semibold border-b border-slate-200 dark:border-zinc-800">
                                <tr>
                                    <th className="px-6 py-4">Feature Flag</th>
                                    <th className="px-6 py-4 text-center w-[120px]">Status</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-slate-100 dark:divide-zinc-800">
                                {featureFlags.map((flag) => (
                                    <tr
                                        key={flag.id}
                                        className="hover:bg-slate-50 dark:hover:bg-zinc-800/30 transition-colors"
                                    >
                                        <td className="px-6 py-4 font-mono text-slate-700 dark:text-slate-300">
                                            {flag.feature}
                                        </td>
                                        <td className="px-6 py-4 text-center">
                                            <Switch
                                                checked={flag.enabled}
                                                onCheckedChange={(checked) => handleToggle(flag.feature, checked)}
                                                disabled={!isEditMode || toggleMutation.isPending}
                                            />
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                )}

                {!flagsLoading && !flagsError && featureFlags.length === 0 && (
                    <p className="text-slate-500 italic p-4 text-center bg-slate-50 dark:bg-zinc-800/50 rounded-lg">
                        No feature flags found.
                    </p>
                )}
            </CardContent>
        </Card>
    )
}

export default FeatureFlagsManager
