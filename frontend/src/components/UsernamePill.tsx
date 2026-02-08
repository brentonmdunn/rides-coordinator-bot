import { useState } from 'react'
import { useCopyToClipboard } from '../lib/utils'

interface UsernamePillProps {
    username: string
    displayName?: string
}

export function UsernamePill({ username, displayName }: UsernamePillProps) {
    const { copyToClipboard } = useCopyToClipboard()
    const [isCopied, setIsCopied] = useState(false)

    const handleCopy = () => {
        copyToClipboard("@" + username)
        setIsCopied(true)
        setTimeout(() => {
            setIsCopied(false)
        }, 5000)
    }

    const nameToShow = displayName || username

    return (
        <span
            onClick={handleCopy}
            className={`px-2 py-1 rounded text-sm cursor-pointer transition-all duration-300 border ${isCopied
                ? 'bg-green-100 dark:bg-green-900/30 text-green-800 dark:text-green-300 border-green-300 dark:border-green-700'
                : 'bg-slate-100 dark:bg-zinc-800 text-slate-700 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-zinc-700 border-transparent'
                }`}
            title={isCopied ? '✓ Copied!' : 'Click to copy username'}
        >
            {nameToShow}
        </span>
    )
}
