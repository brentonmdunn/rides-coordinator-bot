import { useQuery } from '@tanstack/react-query'
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
    const { data, isLoading, error } = useQuery<CacheStatsResponse>({
        queryKey: ['cacheStats'],
        queryFn: async () => {
            const res = await apiFetch('/api/cache/stats')
            if (!res.ok) throw new Error('Failed to load cache stats')
            return res.json()
        },
        refetchInterval: 30000,
    })

    const stats = data?.stats ?? {}
    const namespaces = Object.keys(stats)

    return (
        <Card>
            <CardHeader>
                <CardTitle className="flex items-center gap-2">
                    <span>📊</span>
                    <span>Cache Stats</span>
                </CardTitle>
            </CardHeader>
            <CardContent>
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
                                                                    className={`font-semibold tabular-nums ${
                                                                        fn.hit_rate >= 0.8
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
