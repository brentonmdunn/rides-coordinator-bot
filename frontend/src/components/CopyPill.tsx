import { useState } from 'react'
import { useCopyToClipboard } from '../lib/utils'

interface CopyPillProps {
    copyStr: string
    displayStr: string
}

export function CopyPill({ copyStr, displayStr }: CopyPillProps) {
    const { copyToClipboard } = useCopyToClipboard()
    const [isCopied, setIsCopied] = useState(false)

    const handleCopy = () => {
        copyToClipboard(copyStr)
        setIsCopied(true)
        setTimeout(() => {
            setIsCopied(false)
        }, 5000)
    }


    return (
        <span
            onClick={handleCopy}
            className={`px-2 py-1 rounded text-sm cursor-pointer transition-all duration-300 border ${isCopied
                ? 'bg-success/15 text-success-text border-success/30'
                : 'bg-muted text-foreground hover:bg-muted/80 border-transparent'
                }`}
            title={isCopied ? '✓ Copied!' : 'Click to copy username'}
        >
            {displayStr}
        </span>
    )
}
