import { copyToClipboard } from '../lib/utils'

interface CopyPillProps {
    copyStr: string
    displayStr: string
}

export function CopyPill({ copyStr, displayStr }: CopyPillProps) {
    return (
        <button
            type="button"
            onClick={() => copyToClipboard(copyStr)}
            className="px-2 py-1 rounded text-sm cursor-pointer transition-all duration-300 border bg-muted text-foreground hover:bg-muted/80 border-transparent"
            title="Click to copy username"
            aria-label={`Copy ${displayStr} to clipboard`}
        >
            {displayStr}
        </button>
    )
}
