import { useMemo, useRef, useState, useCallback } from 'react'
import { Button } from './ui/button'
import type { UsernameEntry } from '../hooks/useUsernames'
import {
    COPY_FEEDBACK_MS,
    MENTION_DROPDOWN_MAX_HEIGHT,
    MENTION_DROPDOWN_LINE_HEIGHT_FALLBACK,
    MENTION_DROPDOWN_OFFSET,
} from '../lib/constants'

interface EditableOutputProps {
    value: string
    originalValue: string
    onChange: (value: string) => void
    onCopy: () => void
    onRevert: () => void
    minHeight?: string
    placeholder?: string
    usernames?: UsernameEntry[]
}

// Returns true when the cursor is sitting inside a token that is already a
// valid @mention — so the dropdown should be suppressed.
function isInsideValidMention(value: string, cursorPos: number, validUsernameSet: Set<string>): boolean {
    let atPos = -1
    for (let i = cursorPos - 1; i >= 0; i--) {
        const ch = value[i]
        if (ch === '@') { atPos = i; break }
        if (ch === ' ' || ch === '\n') break
    }
    if (atPos === -1) return false
    if (atPos > 0 && value[atPos - 1] !== ' ' && value[atPos - 1] !== '\n') return false
    let end = cursorPos
    while (end < value.length && value[end] !== ' ' && value[end] !== '\n') end++
    return validUsernameSet.has(value.slice(atPos + 1, end).toLowerCase())
}

function getMentionQuery(value: string, cursorPos: number): string | null {
    for (let i = cursorPos - 1; i >= 0; i--) {
        const ch = value[i]
        if (ch === '@') {
            const before = i > 0 ? value[i - 1] : null
            if (before === null || before === ' ' || before === '\n') {
                return value.slice(i + 1, cursorPos)
            }
            return null
        }
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

// Measures the pixel position of the character at `atIdx` within `textarea`,
// returned relative to `container`. Uses a hidden mirror div so line-wrapping
// is identical to the real textarea. Relies on offsetTop/offsetLeft (not
// getBoundingClientRect) so the mirror can live off-screen without producing
// huge negative viewport coordinates.
function measureAtPosition(
    textarea: HTMLTextAreaElement,
    container: HTMLElement,
    value: string,
    atIdx: number
): { top: number; left: number } | null {
    const cs = window.getComputedStyle(textarea)

    const mirror = document.createElement('div')
    Object.assign(mirror.style, {
        position: 'absolute',
        top: '0',
        left: '0',
        visibility: 'hidden',
        overflow: 'hidden',
        whiteSpace: 'pre-wrap',
        wordWrap: 'break-word',
        width: cs.width,
        padding: cs.padding,
        border: cs.border,
        font: cs.font,
        lineHeight: cs.lineHeight,
        letterSpacing: cs.letterSpacing,
        boxSizing: cs.boxSizing,
    })
    mirror.textContent = value.slice(0, atIdx)
    const marker = document.createElement('span')
    marker.textContent = '​'
    mirror.appendChild(marker)
    document.body.appendChild(mirror)

    // offsetTop/offsetLeft give position within the mirror div, which maps
    // directly to content coordinates inside the textarea.
    const caretTop = marker.offsetTop
    const caretLeft = marker.offsetLeft
    document.body.removeChild(mirror)

    const textareaRect = textarea.getBoundingClientRect()
    const containerRect = container.getBoundingClientRect()
    const lineHeight = parseFloat(cs.lineHeight) || MENTION_DROPDOWN_LINE_HEIGHT_FALLBACK
    const dropdownMaxH = MENTION_DROPDOWN_MAX_HEIGHT

    // Subtract scrollTop because the textarea may have scrolled.
    const relTop = textareaRect.top - containerRect.top + caretTop - textarea.scrollTop
    const relLeft = textareaRect.left - containerRect.left + caretLeft

    const spaceBelow = containerRect.height - relTop - lineHeight
    if (spaceBelow >= dropdownMaxH || spaceBelow >= relTop) {
        return { top: relTop + lineHeight + MENTION_DROPDOWN_OFFSET, left: relLeft }
    }
    return { top: relTop - dropdownMaxH - MENTION_DROPDOWN_OFFSET, left: relLeft }
}

function EditableOutput({
    value,
    originalValue,
    onChange,
    onCopy,
    onRevert,
    minHeight = 'min-h-[80px]',
    placeholder = '',
    usernames,
}: EditableOutputProps) {
    const isModified = value !== originalValue
    const containerRef = useRef<HTMLDivElement>(null)
    const textareaRef = useRef<HTMLTextAreaElement>(null)
    const highlightRef = useRef<HTMLDivElement>(null)
    const [copied, setCopied] = useState(false)
    const [cursorPos, setCursorPos] = useState(0)
    const [activeIndex, setActiveIndex] = useState(0)
    const [dropdownOpen, setDropdownOpen] = useState(true)
    const [dropdownPos, setDropdownPos] = useState<{ top: number; left: number } | null>(null)
    const [height, setHeight] = useState<number | null>(null)
    const dragStartY = useRef<number>(0)
    const dragStartH = useRef<number>(0)

    const startResize = useCallback((e: React.MouseEvent) => {
        e.preventDefault()
        const wrapEl = textareaRef.current?.parentElement
        dragStartY.current = e.clientY
        dragStartH.current = wrapEl?.offsetHeight ?? height ?? 80
        function onMove(ev: MouseEvent) {
            const delta = ev.clientY - dragStartY.current
            setHeight(Math.max(80, dragStartH.current + delta))
        }
        function onUp() {
            document.removeEventListener('mousemove', onMove)
            document.removeEventListener('mouseup', onUp)
        }
        document.addEventListener('mousemove', onMove)
        document.addEventListener('mouseup', onUp)
    }, [height])

    const validUsernameSet = useMemo(
        () => new Set((usernames ?? []).map((u) => u.username.toLowerCase())),
        [usernames]
    )

    const highlightedContent = useMemo(() => {
        if (!usernames) return [value]
        const parts = value.split(/(@\S+)/g)
        return parts.map((part, i) => {
            const prev = parts[i - 1] ?? ''
            const precededBySpace = prev === '' || /\s$/.test(prev)
            if (
                precededBySpace &&
                part.startsWith('@') &&
                validUsernameSet.has(part.slice(1).toLowerCase())
            ) {
                return (
                    <span
                        key={i}
                        className={copied
                            ? 'bg-emerald-400 dark:bg-emerald-500 rounded transition-colors duration-150'
                            : 'bg-emerald-100 dark:bg-emerald-900/40 rounded transition-colors duration-300'}
                    >
                        {part}
                    </span>
                )
            }
            return <span key={i}>{part}</span>
        })
    }, [value, usernames, validUsernameSet, copied])

    const mentionQuery = usernames ? getMentionQuery(value, cursorPos) : null
    const suggestions: UsernameEntry[] =
        mentionQuery !== null && usernames
            ? usernames
                  .filter(({ username, name }) => {
                      const q = mentionQuery.toLowerCase()
                      return username.toLowerCase().includes(q) || name.toLowerCase().includes(q)
                  })
                  .map((entry) => {
                      const q = mentionQuery.toLowerCase()
                      const u = entry.username.toLowerCase()
                      const n = entry.name.toLowerCase()
                      const score =
                          u === q || n === q ? 0
                          : u.startsWith(q) || n.startsWith(q) ? 1
                          : 2
                      return { entry, score }
                  })
                  .sort((a, b) => a.score - b.score)
                  .map(({ entry }) => entry)
            : []
    const insideValidMention = usernames
        ? isInsideValidMention(value, cursorPos, validUsernameSet)
        : false
    const showDropdown = dropdownOpen && mentionQuery !== null && !insideValidMention

    function refreshDropdownPos(text: string, cursor: number) {
        const query = getMentionQuery(text, cursor)
        if (query === null || !textareaRef.current || !containerRef.current) {
            setDropdownPos(null)
            return
        }
        const atIdx = cursor - query.length - 1
        setDropdownPos(measureAtPosition(textareaRef.current, containerRef.current, text, atIdx))
    }

    function updateCursor() {
        const pos = textareaRef.current?.selectionStart ?? 0
        setCursorPos(pos)
        setActiveIndex(0)
        setDropdownOpen(true)
        refreshDropdownPos(value, pos)
    }

    function handleChange(e: React.ChangeEvent<HTMLTextAreaElement>) {
        const newValue = e.target.value
        const newCursor = e.target.selectionStart ?? 0
        onChange(newValue)
        setCursorPos(newCursor)
        setActiveIndex(0)
        setDropdownOpen(true)
        refreshDropdownPos(newValue, newCursor)
    }

    function handleScroll(e: React.UIEvent<HTMLTextAreaElement>) {
        if (highlightRef.current) {
            highlightRef.current.scrollTop = e.currentTarget.scrollTop
            highlightRef.current.scrollLeft = e.currentTarget.scrollLeft
        }
    }

    function commitSuggestion(entry: UsernameEntry) {
        if (mentionQuery === null) return
        const { newValue, newCursor } = applyMention(value, cursorPos, mentionQuery, entry.username)
        onChange(newValue)
        setDropdownOpen(false)
        setDropdownPos(null)
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
        <div
            ref={containerRef}
            className="group relative bg-muted/50 rounded-lg border border-border p-1 transition-all hover:shadow-md hover:border-border/70"
        >
            <div className="absolute top-2 right-2 z-10 flex gap-2 opacity-100 sm:opacity-0 sm:group-hover:opacity-100 sm:group-focus-within:opacity-100 transition-opacity">
                {isModified && (
                    <Button
                        type="button"
                        onClick={onRevert}
                        variant="outline"
                        size="sm"
                        className="h-8 px-2 text-xs border-amber-200 text-amber-700 hover:bg-amber-50 hover:text-amber-800 bg-card dark:border-amber-700 dark:text-amber-400 dark:hover:bg-amber-950"
                    >
                        ↩ Revert
                    </Button>
                )}
                <Button
                    type="button"
                    onClick={() => { onCopy(); setCopied(true); setTimeout(() => setCopied(false), COPY_FEEDBACK_MS) }}
                    size="sm"
                    variant={copied ? 'default' : 'outline'}
                    className={`h-8 px-2 text-xs bg-card hover:bg-muted ${
                        copied
                            ? 'bg-emerald-600 hover:bg-emerald-700 text-white border-transparent dark:bg-emerald-600 dark:hover:bg-emerald-700'
                            : 'text-foreground'
                    }`}
                >
                    {copied ? 'Copied!' : 'Copy'}
                </Button>
            </div>

            {/* Overlay wrapper: highlight div behind, textarea on top */}
            <div
                className="relative"
                style={height !== null ? { height } : undefined}
            >
                {/* Highlight layer — mirrors textarea content with styled @mentions */}
                <div
                    ref={highlightRef}
                    aria-hidden
                    className={`absolute inset-0 ${height === null ? minHeight : ''} p-4 text-sm font-mono text-foreground whitespace-pre-wrap break-words overflow-hidden pointer-events-none rounded-md`}
                >
                    {highlightedContent}
                    {/* Extra line so height matches when content ends with \n */}
                    <br />
                </div>

                {/* Textarea — transparent text so highlight shows through */}
                <textarea
                    ref={textareaRef}
                    value={value}
                    onChange={handleChange}
                    onSelect={updateCursor}
                    onKeyDown={handleKeyDown}
                    onScroll={handleScroll}
                    onBlur={() => setDropdownOpen(false)}
                    placeholder={placeholder}
                    spellCheck={false}
                    className={`relative z-10 w-full ${height === null ? minHeight : 'h-full'} p-4 text-sm font-mono bg-transparent border-0 resize-none focus:ring-0 focus:outline-none rounded-md text-transparent caret-slate-800 dark:caret-slate-200`}
                />
            </div>

            {/* Custom resize handle */}
            <div
                onMouseDown={startResize}
                className="flex items-center justify-center h-3 w-full cursor-ns-resize select-none rounded-b-md hover:bg-muted/70 transition-colors"
                title="Drag to resize"
            >
                <svg width="24" height="4" viewBox="0 0 24 4" className="text-muted-foreground/50">
                    <line x1="4" y1="1.5" x2="20" y2="1.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
                    <line x1="4" y1="3.5" x2="20" y2="3.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
                </svg>
            </div>

            {showDropdown && dropdownPos && (
                <ul
                    style={{ top: dropdownPos.top, left: dropdownPos.left }}
                    className="absolute z-20 w-56 max-h-[9.5rem] overflow-y-auto rounded-md border border-border bg-popover shadow-lg py-1 text-sm"
                >
                    {suggestions.length === 0 ? (
                        <li className="px-3 py-1.5 text-muted-foreground select-none">
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
                                        : 'text-foreground hover:bg-muted'
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
