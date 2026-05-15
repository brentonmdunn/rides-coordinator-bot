import { Component, type ErrorInfo, type ReactNode } from 'react'

interface Props {
    children: ReactNode
    fallback?: ReactNode
}

interface State {
    hasError: boolean
    error: Error | null
}

export default class ErrorBoundary extends Component<Props, State> {
    constructor(props: Props) {
        super(props)
        this.state = { hasError: false, error: null }
    }

    static getDerivedStateFromError(error: Error): State {
        return { hasError: true, error }
    }

    componentDidCatch(error: Error, info: ErrorInfo) {
        console.error('ErrorBoundary caught:', error, info.componentStack)
    }

    render() {
        if (this.state.hasError) {
            if (this.props.fallback !== undefined) {
                return this.props.fallback
            }
            return (
                <div className="min-h-screen flex items-center justify-center p-8">
                    <div className="max-w-md w-full p-6 rounded-lg border border-destructive/30 bg-destructive/10">
                        <h2 className="text-lg font-semibold text-destructive-text mb-2">
                            Something went wrong
                        </h2>
                        <p className="text-sm text-destructive-text mb-4">
                            {this.state.error?.message || 'An unexpected error occurred.'}
                        </p>
                        <button
                            onClick={() => window.location.reload()}
                            className="px-4 py-2 text-sm font-medium rounded-md bg-destructive text-white hover:bg-destructive/90 transition-colors"
                        >
                            Reload page
                        </button>
                    </div>
                </div>
            )
        }

        return this.props.children
    }
}
