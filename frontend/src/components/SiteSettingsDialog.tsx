import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Settings } from 'lucide-react'
import { apiFetch } from '../lib/api'
import type { FellowshipSeason } from '../types'
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
} from './ui/dialog'

interface SiteSettingsDialogProps {
    open: boolean
    onOpenChange: (open: boolean) => void
    canManage: boolean
}

function SiteSettingsDialog({ open, onOpenChange, canManage }: SiteSettingsDialogProps) {
    const queryClient = useQueryClient()

    const { data: seasonData } = useQuery<{ season: FellowshipSeason }>({
        queryKey: ['fellowshipSeason'],
        queryFn: async () => {
            const response = await apiFetch('/api/ask-rides/fellowship-season')
            return response.json()
        },
        enabled: open,
    })

    const season = seasonData?.season ?? 'friday'

    const seasonMutation = useMutation({
        mutationFn: async (newSeason: FellowshipSeason) => {
            const response = await apiFetch('/api/ask-rides/fellowship-season', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ season: newSeason }),
            })
            return response.json()
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['fellowshipSeason'] })
            queryClient.invalidateQueries({ queryKey: ['askRidesStatus'] })
        },
    })

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="sm:max-w-sm">
                <DialogHeader>
                    <DialogTitle className="flex items-center gap-2">
                        <Settings className="h-4 w-4" />
                        Site Settings
                    </DialogTitle>
                </DialogHeader>

                <div className="space-y-4">
                    <div>
                        <p className="text-sm font-medium text-foreground mb-2">Fellowship night</p>
                        <p className="text-xs text-muted-foreground mb-3">
                            Controls which fellowship ride job is active and shown on the dashboard.
                        </p>
                        <div className="inline-flex rounded-md border border-border overflow-hidden">
                            <button
                                onClick={() => seasonMutation.mutate('friday')}
                                disabled={seasonMutation.isPending || !canManage}
                                className={`px-3 py-1.5 text-sm font-medium transition-colors border-r border-border ${
                                    season === 'friday'
                                        ? 'bg-info/15 text-info-text'
                                        : 'bg-background text-muted-foreground hover:bg-muted'
                                } disabled:opacity-50 disabled:cursor-not-allowed`}
                            >
                                🎓 Friday Fellowship
                            </button>
                            <button
                                onClick={() => seasonMutation.mutate('wednesday')}
                                disabled={seasonMutation.isPending || !canManage}
                                className={`px-3 py-1.5 text-sm font-medium transition-colors ${
                                    season === 'wednesday'
                                        ? 'bg-info/15 text-info-text'
                                        : 'bg-background text-muted-foreground hover:bg-muted'
                                } disabled:opacity-50 disabled:cursor-not-allowed`}
                            >
                                ☀️ Wed. Fellowship
                            </button>
                        </div>
                        {seasonMutation.isError && (
                            <p className="mt-2 text-xs text-destructive-text">Failed to switch — try again</p>
                        )}
                        {!canManage && (
                            <p className="mt-2 text-xs text-muted-foreground">Admin access required to change this setting.</p>
                        )}
                    </div>
                </div>
            </DialogContent>
        </Dialog>
    )
}

export default SiteSettingsDialog
