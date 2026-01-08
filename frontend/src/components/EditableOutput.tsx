import { Button } from './ui/button'

interface EditableOutputProps {
    value: string
    originalValue: string
    onChange: (value: string) => void
    onCopy: () => void
    onRevert: () => void
    copied: boolean
    minHeight?: string
    placeholder?: string
}

/**
 * Reusable component for editable text output with copy and revert functionality.
 * Used in RouteBuilder and GroupRides for consistent UX.
 */
function EditableOutput({
    value,
    originalValue,
    onChange,
    onCopy,
    onRevert,
    copied,
    minHeight = 'min-h-[80px]',
    placeholder = ''
}: EditableOutputProps) {
    const isModified = value !== originalValue

    return (
        <div className="group relative bg-slate-50 dark:bg-zinc-800/50 rounded-lg border border-slate-200 dark:border-zinc-700 p-1 transition-all hover:shadow-md hover:border-slate-300 dark:hover:border-zinc-600">
            <div className="absolute top-2 right-2 z-10 flex gap-2 opacity-100 sm:opacity-0 sm:group-hover:opacity-100 transition-opacity">
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
                    variant={copied ? "default" : "outline"}
                    className={`h-8 px-2 text-xs bg-white hover:bg-slate-100 dark:bg-zinc-900 ${copied
                        ? "bg-emerald-600 hover:bg-emerald-700 text-white border-transparent dark:bg-emerald-600 dark:hover:bg-emerald-700"
                        : "text-slate-700 dark:text-slate-300"
                        }`}
                >
                    {copied ? '✓ Copied' : '📋 Copy'}
                </Button>
            </div>
            <textarea
                value={value}
                onChange={(e) => onChange(e.target.value)}
                placeholder={placeholder}
                className={`w-full ${minHeight} p-4 text-sm font-mono bg-transparent border-0 resize-y focus:ring-0 focus:outline-none text-slate-800 dark:text-slate-200 rounded-md`}
                spellCheck={false}
            />
        </div>
    )
}

export default EditableOutput
