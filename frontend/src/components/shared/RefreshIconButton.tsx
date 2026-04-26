import { RefreshCw } from 'lucide-react'
import { Button } from '../ui/button'

interface RefreshIconButtonProps {
    onClick: () => void
    /** When true, the icon spins and the button is disabled. */
    isLoading?: boolean
    /** Tooltip + accessible label. Defaults to "Refresh data". */
    title?: string
}

/**
 * Compact ghost button used in card headers to refresh widget data.
 */
function RefreshIconButton({
    onClick,
    isLoading = false,
    title = 'Refresh data',
}: RefreshIconButtonProps) {
    return (
        <Button
            variant="ghost"
            size="sm"
            onClick={onClick}
            title={title}
            aria-label={title}
            className="h-8 w-8 p-0"
            disabled={isLoading}
        >
            <RefreshCw className={`h-4 w-4 ${isLoading ? 'animate-spin' : ''}`} />
        </Button>
    )
}

export default RefreshIconButton
