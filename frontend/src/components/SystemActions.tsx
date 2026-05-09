import { useMutation } from '@tanstack/react-query'
import { apiFetch } from '../lib/api'
import { useState } from 'react'
import { RefreshCw } from 'lucide-react'
import { Button } from './ui/button'
import ConfirmDialog from './ConfirmDialog'
import { SectionCard } from './shared'

function SystemActions() {
    const [showConfirm, setShowConfirm] = useState(false)

    const invalidateMutation = useMutation({
        mutationFn: async () => {
            const res = await apiFetch('/api/cache/invalidate', { method: 'POST' })
            return res.json()
        },
    })

    const handleInvalidate = () => {
        setShowConfirm(false)
        invalidateMutation.mutate()
    }

    return (
        <SectionCard
            icon="⚠️"
            title="System Actions"
            titleClassName="text-destructive-text"
        >
                <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
                    <div className="text-sm text-muted-foreground text-center sm:text-left">
                        Clear all cached data. This will force the system to fetch fresh data from the database and other external sources on the next request. This may temporarily increase load times.
                    </div>
                    <Button
                        onClick={() => setShowConfirm(true)}
                        disabled={invalidateMutation.isPending}
                        variant="destructive"
                        className="whitespace-nowrap gap-2"
                    >
                        <RefreshCw className={`w-4 h-4 ${invalidateMutation.isPending ? 'animate-spin' : ''}`} />
                        {invalidateMutation.isPending ? 'Invalidating...' : 'Invalidate All Cache'}
                    </Button>
                </div>
                {invalidateMutation.isError && (
                    <div className="mt-4 px-3 py-2 rounded-md bg-destructive/10 border border-destructive/30 text-destructive-text text-sm">
                        ❌ {invalidateMutation.error instanceof Error ? invalidateMutation.error.message : 'Failed to invalidate cache'}
                    </div>
                )}
                {invalidateMutation.isSuccess && (
                    <div className="mt-4 px-3 py-2 rounded-md bg-success/15 border border-success/30 text-success-text text-sm">
                        ✅ All cache entries invalidated successfully.
                    </div>
                )}
            <ConfirmDialog
                isOpen={showConfirm}
                title="Invalidate all cache entries?"
                description="This will clear all cached data. This will force the system to fetch fresh data from the database and other external sources on the next request. This may temporarily increase load times."
                confirmText="Yes, invalidate cache"
                confirmVariant="destructive"
                onConfirm={handleInvalidate}
                onCancel={() => setShowConfirm(false)}
            />
        </SectionCard>
    )
}

export default SystemActions
