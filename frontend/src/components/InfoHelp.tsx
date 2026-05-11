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
                ? 'text-info-text bg-info/10'
                : 'text-muted-foreground hover:text-foreground'
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
        <div className="mb-6 p-4 bg-info/10 border border-info/30 rounded-lg relative animate-in fade-in slide-in-from-top-2 duration-200">
            <button
                onClick={onClose}
                className="absolute top-2 right-2 text-info/70 hover:text-info transition-colors"
                title="Close info"
            >
                <X className="h-4 w-4" />
                <span className="sr-only">Close info</span>
            </button>
            <h4 className="font-semibold text-info-text mb-2 text-sm flex items-center gap-2">
                <Info className="h-4 w-4" />
                {title}
            </h4>
            <div className="text-sm text-info-text ml-1">
                {children}
            </div>
        </div>
    )
}
