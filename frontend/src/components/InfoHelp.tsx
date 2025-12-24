import { Button } from './ui/button'
import { Info, X } from 'lucide-react'
import type { ReactNode } from 'react'

interface InfoToggleButtonProps {
    isOpen: boolean
    onClick: () => void
    title?: string
}

export function InfoToggleButton({ isOpen, onClick, title = "How to use" }: InfoToggleButtonProps) {
    return (
        <Button
            variant="ghost"
            size="icon"
            onClick={onClick}
            className={`h-8 w-8 transition-colors ${isOpen
                ? 'text-blue-600 bg-blue-50 dark:bg-blue-900/20 dark:text-blue-300'
                : 'text-slate-500 hover:text-slate-900 dark:text-slate-400 dark:hover:text-slate-100'
                }`}
            title={title}
        >
            <Info className="h-5 w-5" />
            <span className="sr-only">{title}</span>
        </Button>
    )
}

interface InfoPanelProps {
    isOpen: boolean
    onClose: () => void
    title: string
    children: ReactNode
}

export function InfoPanel({ isOpen, onClose, title, children }: InfoPanelProps) {
    if (!isOpen) return null

    return (
        <div className="mb-6 p-4 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg relative animate-in fade-in slide-in-from-top-2 duration-200">
            <button
                onClick={onClose}
                className="absolute top-2 right-2 text-blue-400 hover:text-blue-600 dark:text-blue-400 dark:hover:text-blue-300 transition-colors"
                title="Close info"
            >
                <X className="h-4 w-4" />
                <span className="sr-only">Close info</span>
            </button>
            <h4 className="font-semibold text-blue-900 dark:text-blue-300 mb-2 text-sm flex items-center gap-2">
                <Info className="h-4 w-4" />
                {title}
            </h4>
            <div className="text-sm text-blue-800 dark:text-blue-200 ml-1">
                {children}
            </div>
        </div>
    )
}
