import { useRef, useState } from 'react'
import { Button } from './ui/button'
import type { UsernameEntry } from '../hooks/useUsernames'

interface EditableOutputProps {
    value: string
    originalValue: string
    onChange: (value: string) => void
    onCopy: () => void
    onRevert: () => void
    copied: boolean
    minHeight?: string
    placeholder?: string
    usernames?: UsernameEntry[]
}

const MAX_SUGGESTIONS = 5

function getMentionQuery(value: string, cursorPos: number): string | null {
    for (let i = cursorPos - 1; i >= 0; i--) {
        const ch = value[i]
        if (ch === '@') return value.slice(i + 1, cursorPos)
        if (ch === ' ' || ch === '\n') return null
    }
    return null
}

function applyMention(
    value: string,
    cursorPos: number,
    query: string,
    username: string
): { newValue: string; newCursor: number } {
    const atPos = cursorPos - query.length - 1
    const trailingSpace = value[cursorPos] === ' ' ? '' : ' '
    const insertion = `@${username}${trailingSpace}`
    const newValue = value.slice(0, atPos) + insertion + value.slice(cursorPos)
    return { newValue, newCursor: atPos + insertion.length }
}

function EditableOutput({
    value,
    originalValue,
    onChange,
    onCopy,
    onRevert,
    copied,
    minHeight = 'min-h-[80px]',
    placeholder = '',
    usernames,
}: EditableOutputProps) {
    const isModified = value !== originalValue
    const textareaRef = useRef<HTMLTextAreaElement>(null)
    const [cursorPos, setCursorPos] = useState(0)
    const [activeIndex, setActiveIndex] = useState(0)
    const [dropdownOpen, setDropdownOpen] = useState(true)

    const mentionQuery = usernames ? getMentionQuery(value, cursorPos) : null
    const suggestions: UsernameEntry[] =
        mentionQuery !== null && usernames
            ? usernames
                  .filter(({ username, name }) => {
                      const q = mentionQuery.toLowerCase()
                      return username.toLowerCase().includes(q) || name.toLowerCase().includes(q)
                  })
                  .slice(0, MAX_SUGGESTIONS)
            : []
    const showDropdown = dropdownOpen && mentionQuery !== null

    function updateCursor() {
        const pos = textareaRef.current?.selectionStart ?? 0
        setCursorPos(pos)
        setActiveIndex(0)
        setDropdownOpen(true)
    }

    function handleChange(e: React.ChangeEvent<HTMLTextAreaElement>) {
        onChange(e.target.value)
        setCursorPos(e.target.selectionStart ?? 0)
        setActiveIndex(0)
        setDropdownOpen(true)
    }

    function commitSuggestion(entry: UsernameEntry) {
        if (mentionQuery === null) return
        const { newValue, newCursor } = applyMention(value, cursorPos, mentionQuery, entry.username)
        onChange(newValue)
        setDropdownOpen(false)
        // Restore focus and cursor after React re-renders
        requestAnimationFrame(() => {
            if (textareaRef.current) {
                textareaRef.current.focus()
                textareaRef.current.setSelectionRange(newCursor, newCursor)
                setCursorPos(newCursor)
            }
        })
    }

    function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
        if (!showDropdown || suggestions.length === 0) return

        if (e.key === 'ArrowDown') {
            e.preventDefault()
            setActiveIndex((i) => (i + 1) % suggestions.length)
        } else if (e.key === 'ArrowUp') {
            e.preventDefault()
            setActiveIndex((i) => (i - 1 + suggestions.length) % suggestions.length)
        } else if (e.key === 'Enter') {
            e.preventDefault()
            commitSuggestion(suggestions[activeIndex] as UsernameEntry)
        } else if (e.key === 'Escape') {
            setDropdownOpen(false)
        }
    }

    return (
        <div className="group relative bg-slate-50 dark:bg-zinc-800/50 rounded-lg border border-slate-200 dark:border-zinc-700 p-1 transition-all hover:shadow-md hover:border-slate-300 dark:hover:border-zinc-600">
            <div className="absolute top-2 right-2 z-10 flex gap-2 opacity-100 sm:opacity-0 sm:group-hover:opacity-100 sm:group-focus-within:opacity-100 transition-opacity">
                {isModified && (
                    <Button
                        onClick={onRevert}
                        variant="outline"
                        size="sm"
                        className="h-8 px-2 text-xs border-amber-200 text-amber-700 hover:bg-amber-50 hover:text-amber-800 bg-white dark:bg-zinc-900 dark:border-amber-700 dark:text-amber-400 dark:hover:bg-amber-950"
                    >
                        ↩ Revert
                    </Button>
                )}
                <Button
                    onClick={onCopy}
                    size="sm"
                    variant={copied ? 'default' : 'outline'}
                    className={`h-8 px-2 text-xs bg-white hover:bg-slate-100 dark:bg-zinc-900 ${
                        copied
                            ? 'bg-emerald-600 hover:bg-emerald-700 text-white border-transparent dark:bg-emerald-600 dark:hover:bg-emerald-700'
                            : 'text-slate-700 dark:text-slate-300'
                    }`}
                >
                    {copied ? '✓ Copied' : '📋 Copy'}
                </Button>
            </div>
            <textarea
                ref={textareaRef}
                value={value}
                onChange={handleChange}
                onSelect={updateCursor}
                onKeyDown={handleKeyDown}
                onBlur={() => setDropdownOpen(false)}
                placeholder={placeholder}
                className={`w-full ${minHeight} p-4 text-sm font-mono bg-transparent border-0 resize-y focus:ring-0 focus:outline-none text-slate-800 dark:text-slate-200 rounded-md`}
                spellCheck={false}
            />
            {showDropdown && (
                <ul className="absolute bottom-2 left-2 z-20 w-56 rounded-md border border-slate-200 dark:border-zinc-600 bg-white dark:bg-zinc-900 shadow-lg py-1 text-sm">
                    {suggestions.length === 0 ? (
                        <li className="px-3 py-1.5 text-slate-400 dark:text-slate-500 select-none">
                            No results
                        </li>
                    ) : (
                        suggestions.map((entry, i) => (
                            <li
                                key={entry.username}
                                onMouseDown={(e) => {
                                    e.preventDefault()
                                    commitSuggestion(entry)
                                }}
                                className={`px-3 py-1.5 cursor-pointer select-none ${
                                    i === activeIndex
                                        ? 'bg-emerald-50 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-300'
                                        : 'text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-zinc-800'
                                }`}
                            >
                                @{entry.username}
                            </li>
                        ))
                    )}
                </ul>
            )}
        </div>
    )
}

export default EditableOutput
