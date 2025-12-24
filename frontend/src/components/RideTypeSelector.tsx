type RideType = 'friday' | 'sunday' | 'message_id'

interface RideTypeSelectorProps {
    value: RideType
    onChange: (value: RideType) => void
}

export default function RideTypeSelector({ value, onChange }: RideTypeSelectorProps) {
    return (
        <div className="mb-6">
            <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                Select Ride Type
            </label>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <button
                    type="button"
                    onClick={() => onChange('friday')}
                    className={`
                        flex items-center justify-center gap-2 px-4 py-3 rounded-lg border text-sm font-medium transition-all
                        ${value === 'friday'
                            ? 'bg-blue-50 border-blue-500 text-blue-700 dark:bg-blue-950/30 dark:border-blue-500 dark:text-blue-300 ring-1 ring-blue-500'
                            : 'bg-white border-slate-200 text-slate-700 hover:bg-slate-50 hover:border-slate-300 dark:bg-zinc-900 dark:border-zinc-800 dark:text-slate-300 dark:hover:bg-zinc-800'
                        }
                    `}
                >
                    <span className="text-lg">🎉</span>
                    <span>Friday Fellowship</span>
                </button>

                <button
                    type="button"
                    onClick={() => onChange('sunday')}
                    className={`
                        flex items-center justify-center gap-2 px-4 py-3 rounded-lg border text-sm font-medium transition-all
                        ${value === 'sunday'
                            ? 'bg-blue-50 border-blue-500 text-blue-700 dark:bg-blue-950/30 dark:border-blue-500 dark:text-blue-300 ring-1 ring-blue-500'
                            : 'bg-white border-slate-200 text-slate-700 hover:bg-slate-50 hover:border-slate-300 dark:bg-zinc-900 dark:border-zinc-800 dark:text-slate-300 dark:hover:bg-zinc-800'
                        }
                    `}
                >
                    <span className="text-lg">⛪</span>
                    <span>Sunday Service</span>
                </button>

                <button
                    type="button"
                    onClick={() => onChange('message_id')}
                    className={`
                        flex items-center justify-center gap-2 px-4 py-3 rounded-lg border text-sm font-medium transition-all
                        ${value === 'message_id'
                            ? 'bg-blue-50 border-blue-500 text-blue-700 dark:bg-blue-950/30 dark:border-blue-500 dark:text-blue-300 ring-1 ring-blue-500'
                            : 'bg-white border-slate-200 text-slate-700 hover:bg-slate-50 hover:border-slate-300 dark:bg-zinc-900 dark:border-zinc-800 dark:text-slate-300 dark:hover:bg-zinc-800'
                        }
                    `}
                >
                    <span className="text-lg">🔢</span>
                    <span>Custom Message ID</span>
                </button>
            </div>
        </div>
    )
}

export type { RideType }
