import { Settings } from 'lucide-react'
import { Button } from '../ui/button'

interface SettingsToggleButtonProps {
    isOpen: boolean
    onClick: () => void
    title?: string
}

/**
 * Compact ghost button that toggles an "Advanced Settings" section. Highlights
 * itself when the section is open.
 */
function SettingsToggleButton({
    isOpen,
    onClick,
    title = 'Advanced Settings',
}: SettingsToggleButtonProps) {
    return (
        <Button
            variant="ghost"
            size="icon"
            onClick={onClick}
            className={`h-8 w-8 transition-colors ${isOpen
                ? 'bg-accent text-accent-foreground'
                : 'text-muted-foreground hover:text-foreground'
                }`}
            title={title}
            aria-label={title}
        >
            <Settings className="h-4 w-4" />
        </Button>
    )
}

export default SettingsToggleButton
