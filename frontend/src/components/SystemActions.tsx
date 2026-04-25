import { useMutation } from '@tanstack/react-query'
import { apiFetch } from '../lib/api'
import { useState } from 'react'
import { Card, CardHeader, CardTitle, CardContent } from './ui/card'
import { RefreshCw } from 'lucide-react'
import ConfirmDialog from './ConfirmDialog'

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
        <Card>
            <CardHeader>
                <CardTitle className="flex items-center gap-2 text-red-600 dark:text-red-400">
                    <span>⚠️</span>
                    <span>System Actions</span>
                </CardTitle>
            </CardHeader>
            <CardContent>
                <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
                    <div className="text-sm text-slate-600 dark:text-slate-400 text-center sm:text-left">
                        Clear all cached data. This will force the system to fetch fresh data from the database and other external sources on the next request. This may temporarily increase load times.
                    </div>
                    <button
                        onClick={() => setShowConfirm(true)}
                        disabled={invalidateMutation.isPending}
                        className="whitespace-nowrap inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-red-700 dark:text-red-300 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg hover:bg-red-100 dark:hover:bg-red-900/40 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                        <RefreshCw className={`w-4 h-4 ${invalidateMutation.isPending ? 'animate-spin' : ''}`} />
                        {invalidateMutation.isPending ? 'Invalidating...' : 'Invalidate All Cache'}
                    </button>
                </div>
                {invalidateMutation.isError && (
                    <div className="mt-4 px-3 py-2 rounded-md bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 text-red-700 dark:text-red-300 text-sm">
                        ❌ {invalidateMutation.error instanceof Error ? invalidateMutation.error.message : 'Failed to invalidate cache'}
                    </div>
                )}
                {invalidateMutation.isSuccess && (
                    <div className="mt-4 px-3 py-2 rounded-md bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 text-green-700 dark:text-green-300 text-sm">
                        ✅ All cache entries invalidated successfully.
                    </div>
                )}
            </CardContent>
            <ConfirmDialog
                isOpen={showConfirm}
                title="Invalidate all cache entries?"
                description="This will clear all cached data. This will force the system to fetch fresh data from the database and other external sources on the next request. This may temporarily increase load times."
                confirmText="Yes, invalidate cache"
                confirmButtonClass="bg-red-600 hover:bg-red-700 text-white"
                onConfirm={handleInvalidate}
                onCancel={() => setShowConfirm(false)}
            />
        </Card>
    )
}

export default SystemActions
