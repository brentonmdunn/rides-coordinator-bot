import { copyToClipboard } from '../lib/utils'

interface CopyPillProps {
    copyStr: string
    displayStr: string
    /** 'default' renders the standard muted pill; 'muted' renders a subdued dashed-border pill for non-Discord entries */
    variant?: 'default' | 'muted'
}

export function CopyPill({ copyStr, displayStr, variant = 'default' }: CopyPillProps) {
    const className =
        variant === 'muted'
            ? 'px-2 py-1 rounded text-sm cursor-pointer transition-all duration-300 border border-dashed bg-transparent text-muted-foreground hover:bg-muted/50 border-border'
            : 'px-2 py-1 rounded text-sm cursor-pointer transition-all duration-300 border bg-muted text-foreground hover:bg-muted/80 border-transparent'

    return (
        <button
            type="button"
            onClick={() => copyToClipboard(copyStr)}
            className={className}
            title="Click to copy"
            aria-label={`Copy ${displayStr} to clipboard`}
        >
            {displayStr}
        </button>
    )
}
