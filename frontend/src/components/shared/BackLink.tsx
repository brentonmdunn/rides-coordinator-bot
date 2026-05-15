import { Link } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'

interface BackLinkProps {
    to: string
    label?: string
}

function BackLink({ to, label = 'Back to Dashboard' }: BackLinkProps) {
    return (
        <Link
            to={to}
            className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground mb-4 transition-colors"
        >
            <ArrowLeft className="w-3.5 h-3.5" />
            {label}
        </Link>
    )
}

export default BackLink
