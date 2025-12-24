import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiFetch } from '../lib/api'
import { Switch } from '@/components/ui/switch'
import ErrorMessage from "./ErrorMessage"
import type { FeatureFlag } from '../types'

interface FeatureFlagsResponse {
    flags: FeatureFlag[]
}

function FeatureFlagsManager() {
    const queryClient = useQueryClient()

    // 1. Fetch flags using useQuery
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
        <div className="card" style={{ marginTop: '2em', textAlign: 'left' }}>
            <h2>⚙️ Feature Flags</h2>

            {flagsLoading && <p>Loading feature flags...</p>}

            <ErrorMessage message={flagsError} />

            {!flagsLoading && !flagsError && featureFlags.length > 0 && (
                <table style={{ width: '100%', borderCollapse: 'collapse', marginTop: '1em' }}>
                    <thead>
                        <tr style={{ borderBottom: '2px solid #ccc' }}>
                            <th style={{ textAlign: 'left', padding: '0.75em' }}>Feature Flag</th>
                            <th style={{ textAlign: 'center', padding: '0.75em', width: '100px' }}>Status</th>
                        </tr>
                    </thead>
                    <tbody>
                        {featureFlags.map((flag) => (
                            <tr key={flag.id} style={{ borderBottom: '1px solid #eee' }}>
                                <td style={{ padding: '0.75em', fontFamily: 'monospace' }}>
                                    {flag.feature}
                                </td>
                                <td style={{ padding: '0.75em', textAlign: 'center' }}>
                                    <Switch
                                        checked={flag.enabled}
                                        onCheckedChange={(checked) => handleToggle(flag.feature, checked)}
                                        disabled={toggleMutation.isPending}
                                    />
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            )}

            {!flagsLoading && !flagsError && featureFlags.length === 0 && (
                <p style={{ color: '#666', marginTop: '1em' }}>No feature flags found.</p>
            )}
        </div>
    )
}

export default FeatureFlagsManager
