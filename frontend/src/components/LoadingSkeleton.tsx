import { Skeleton } from './ui/skeleton'

export function TableSkeleton({ rows = 4, cols = 3 }: { rows?: number; cols?: number }) {
    return (
        <div className="rounded-lg border border-border overflow-hidden">
            <div className="bg-muted/50 px-4 py-3 flex gap-4">
                {Array.from({ length: cols }).map((_, i) => (
                    <Skeleton key={i} className="h-4 flex-1" />
                ))}
            </div>
            {Array.from({ length: rows }).map((_, i) => (
                <div key={i} className="px-4 py-3 flex gap-4 border-t border-border">
                    {Array.from({ length: cols }).map((_, j) => (
                        <Skeleton key={j} className="h-4 flex-1" />
                    ))}
                </div>
            ))}
        </div>
    )
}

export function ListSkeleton({ rows = 3 }: { rows?: number }) {
    return (
        <div className="space-y-3">
            {Array.from({ length: rows }).map((_, i) => (
                <div key={i} className="flex items-center gap-3">
                    <Skeleton className="h-4 w-4 rounded-full" />
                    <Skeleton className="h-4 flex-1" />
                </div>
            ))}
        </div>
    )
}

export function GridSkeleton({ count = 6 }: { count?: number }) {
    return (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {Array.from({ length: count }).map((_, i) => (
                <div key={i} className="flex items-center justify-between rounded-xl border border-border bg-muted/30 px-4 py-3">
                    <div className="space-y-1.5 flex-1">
                        <Skeleton className="h-4 w-36" />
                        <Skeleton className="h-3 w-16" />
                    </div>
                    <Skeleton className="h-5 w-10 rounded-full" />
                </div>
            ))}
        </div>
    )
}

export function CoverageSkeleton() {
    return (
        <div className="space-y-3">
            {Array.from({ length: 2 }).map((_, i) => (
                <div key={i} className="border border-border rounded-lg p-4 flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <Skeleton className="h-8 w-8 rounded" />
                        <div className="space-y-2">
                            <Skeleton className="h-4 w-24" />
                            <Skeleton className="h-3 w-32" />
                        </div>
                    </div>
                    <Skeleton className="h-4 w-16" />
                </div>
            ))}
        </div>
    )
}
