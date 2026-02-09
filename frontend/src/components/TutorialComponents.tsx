import type { ReactNode } from 'react'

interface TutorialSectionProps {
    title: string
    children?: ReactNode
}

export function TutorialSection({ title, children }: TutorialSectionProps) {
    return (
        <section className="mb-12">
            <h2 className="text-2xl font-bold text-slate-900 dark:text-white mb-4">
                {title}
            </h2>
            {children}
        </section>
    )
}

interface TutorialSubheaderProps {
    children: ReactNode
}

export function TutorialSubheader({ children }: TutorialSubheaderProps) {
    return (
        <h3 className="text-xl font-semibold text-slate-800 dark:text-slate-200 mt-6 mb-3">
            {children}
        </h3>
    )
}

interface TutorialTextProps {
    children?: ReactNode
}

export function TutorialText({ children }: TutorialTextProps) {
    return (
        <p className="text-slate-600 dark:text-slate-300 leading-relaxed mb-4">
            {children}
        </p>
    )
}
