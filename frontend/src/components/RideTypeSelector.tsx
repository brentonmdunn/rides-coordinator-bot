import { Sparkles, Church, Hash } from 'lucide-react'

type RideType = 'friday' | 'sunday' | 'message_id'

interface RideTypeSelectorProps {
    value: RideType
    onChange: (value: RideType) => void
}

export default function RideTypeSelector({ value, onChange }: RideTypeSelectorProps) {
    return (
        <div className="mb-6">
            <label className="block text-sm font-medium text-foreground mb-2">
                Select Ride Type
            </label>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <button
                    type="button"
                    onClick={() => onChange('friday')}
                    className={`
                        flex items-center justify-center gap-2 px-4 py-3 rounded-lg border text-sm font-medium transition-all
                        ${value === 'friday'
                            ? 'bg-info/10 border-info text-foreground ring-1 ring-info'
                            : 'bg-card border-border text-foreground hover:bg-accent hover:text-accent-foreground'
                        }
                    `}
                >
                    <Sparkles className="h-4 w-4" />
                    <span>Friday Fellowship</span>
                </button>

                <button
                    type="button"
                    onClick={() => onChange('sunday')}
                    className={`
                        flex items-center justify-center gap-2 px-4 py-3 rounded-lg border text-sm font-medium transition-all
                        ${value === 'sunday'
                            ? 'bg-info/10 border-info text-foreground ring-1 ring-info'
                            : 'bg-card border-border text-foreground hover:bg-accent hover:text-accent-foreground'
                        }
                    `}
                >
                    <Church className="h-4 w-4" />
                    <span>Sunday Service</span>
                </button>

                <button
                    type="button"
                    onClick={() => onChange('message_id')}
                    className={`
                        flex items-center justify-center gap-2 px-4 py-3 rounded-lg border text-sm font-medium transition-all
                        ${value === 'message_id'
                            ? 'bg-info/10 border-info text-foreground ring-1 ring-info'
                            : 'bg-card border-border text-foreground hover:bg-accent hover:text-accent-foreground'
                        }
                    `}
                >
                    <Hash className="h-4 w-4" />
                    <span>Custom Message ID</span>
                </button>
            </div>
        </div>
    )
}

export type { RideType }
