import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiFetch } from '../lib/api'
import { Card, CardHeader, CardTitle, CardContent } from './ui/card'

interface FunctionStats {
    func: string
    namespace: string
    size: number
    maxsize: number
    hits: number
    misses: number
    hit_rate: number
}

interface CacheStatsResponse {
    stats: Record<string, FunctionStats[]>
}

function CacheStats() {
    const queryClient = useQueryClient()

    const { data, isLoading, error } = useQuery<CacheStatsResponse>({
        queryKey: ['cacheStats'],
        queryFn: async () => {
            const res = await apiFetch('/api/cache/stats')
            if (!res.ok) throw new Error('Failed to load cache stats')
            return res.json()
        },
        refetchInterval: 30000,
    })

    const invalidateMutation = useMutation({
        mutationFn: async () => {
            const res = await apiFetch('/api/cache/invalidate', { method: 'POST' })
            if (!res.ok) {
                const data = await res.json().catch(() => ({}))
                throw new Error(data.detail || 'Failed to invalidate cache')
            }
            return res.json()
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['cacheStats'] })
        },
    })

    const handleInvalidate = () => {
        if (window.confirm('Are you sure you want to invalidate all cache entries?')) {
            invalidateMutation.mutate()
        }
    }

    const stats = data?.stats ?? {}
    const namespaces = Object.keys(stats)

    return (
        <Card>
            <CardHeader>
                <div className="flex items-center justify-between w-full">
                    <CardTitle className="flex items-center gap-2">
                        <span>📊</span>
                        <span>Cache Stats</span>
                    </CardTitle>
                    <button
                        id="invalidate-all-cache-btn"
                        onClick={handleInvalidate}
                        disabled={invalidateMutation.isPending}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-red-700 dark:text-red-300 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg hover:bg-red-100 dark:hover:bg-red-900/40 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                        🗑️ {invalidateMutation.isPending ? 'Invalidating...' : 'Invalidate All'}
                    </button>
                </div>
            </CardHeader>
            <CardContent>
                {invalidateMutation.isError && (
                    <div className="mb-4 px-3 py-2 rounded-md bg-destructive/15 border border-destructive/30 text-destructive-text text-sm">
                        ❌ {invalidateMutation.error instanceof Error ? invalidateMutation.error.message : 'Failed to invalidate cache'}
                    </div>
                )}

                {invalidateMutation.isSuccess && (
                    <div className="mb-4 px-3 py-2 rounded-md bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 text-green-700 dark:text-green-300 text-sm">
                        ✅ All cache entries invalidated successfully.
                    </div>
                )}

                {isLoading && (
                    <div className="p-8 text-center text-slate-500 animate-pulse">
                        Loading cache stats...
                    </div>
                )}

                {error && (
                    <div className="p-4 text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-900/20 rounded-lg text-sm">
                        {error instanceof Error ? error.message : 'Failed to load cache stats'}
                    </div>
                )}

                {!isLoading && !error && namespaces.length === 0 && (
                    <p className="text-slate-500 italic p-4 text-center bg-slate-50 dark:bg-zinc-800/50 rounded-lg">
                        No cache data available.
                    </p>
                )}

                {!isLoading && !error && namespaces.length > 0 && (
                    <div className="space-y-6">
                        {namespaces.map((ns) => (
                            <div key={ns}>
                                <h3 className="text-sm font-semibold text-slate-600 dark:text-slate-400 mb-2 font-mono">
                                    {ns}
                                </h3>
                                <div className="rounded-lg border border-slate-200 dark:border-zinc-800 overflow-x-auto w-full max-w-[calc(100vw-3rem)]">
                                    <table className="w-full text-left text-sm">
                                        <thead className="bg-slate-50 dark:bg-zinc-800/50 text-slate-900 dark:text-slate-100 font-semibold border-b border-slate-200 dark:border-zinc-800">
                                            <tr>
                                                <th className="px-4 py-3">Function</th>
                                                <th className="px-4 py-3 text-right">Size</th>
                                                <th className="px-4 py-3 text-right">Hits</th>
                                                <th className="px-4 py-3 text-right">Misses</th>
                                                <th className="px-4 py-3 text-right">Hit Rate</th>
                                            </tr>
                                        </thead>
                                        <tbody className="divide-y divide-slate-100 dark:divide-zinc-800">
                                            {stats[ns].map((fn) => {
                                                const total = fn.hits + fn.misses
                                                return (
                                                    <tr
                                                        key={fn.func}
                                                        className="hover:bg-slate-50 dark:hover:bg-zinc-800/30 transition-colors"
                                                    >
                                                        <td className="px-4 py-3 font-mono text-slate-700 dark:text-slate-300">
                                                            {fn.func}
                                                        </td>
                                                        <td className="px-4 py-3 text-right tabular-nums text-slate-600 dark:text-slate-400">
                                                            {fn.size}/{fn.maxsize}
                                                        </td>
                                                        <td className="px-4 py-3 text-right tabular-nums text-green-600 dark:text-green-400">
                                                            {fn.hits.toLocaleString()}
                                                        </td>
                                                        <td className="px-4 py-3 text-right tabular-nums text-amber-600 dark:text-amber-400">
                                                            {fn.misses.toLocaleString()}
                                                        </td>
                                                        <td className="px-4 py-3 text-right">
                                                            {total > 0 ? (
                                                                <span
                                                                    className={`font-semibold tabular-nums ${fn.hit_rate >= 0.8
                                                                            ? 'text-green-600 dark:text-green-400'
                                                                            : fn.hit_rate >= 0.5
                                                                                ? 'text-amber-600 dark:text-amber-400'
                                                                                : 'text-red-600 dark:text-red-400'
                                                                        }`}
                                                                >
                                                                    {(fn.hit_rate * 100).toFixed(1)}%
                                                                </span>
                                                            ) : (
                                                                <span className="text-slate-400">—</span>
                                                            )}
                                                        </td>
                                                    </tr>
                                                )
                                            })}
                                        </tbody>
                                    </table>
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </CardContent>
        </Card>
    )
}

export default CacheStats
