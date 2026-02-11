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

interface TutorialListProps {
    children: ReactNode
}

export function TutorialList({ children }: TutorialListProps) {
    return (
        <ul className="list-disc pl-6 text-slate-600 dark:text-slate-300 leading-relaxed mb-4">
            {children}
        </ul>
    )
}

interface TutorialTableProps {
    headers: string[]
    rows: string[][]
}

export function TutorialTable({ headers, rows }: TutorialTableProps) {
    return (
        <div className="overflow-x-auto mt-4 mb-4">
            <table className="w-full border-collapse text-sm text-left">
                <thead>
                    <tr className="border-b border-slate-300 dark:border-zinc-700">
                        {headers.map((header, i) => (
                            <th key={i} className="py-2 px-4 font-semibold">{header}</th>
                        ))}
                    </tr>
                </thead>
                <tbody>
                    {rows.map((row, i) => (
                        <tr key={i} className="border-b border-slate-200 dark:border-zinc-800">
                            {row.map((cell, j) => (
                                <td key={j} className="py-2 px-4">{cell}</td>
                            ))}
                        </tr>
                    ))}
                </tbody>
            </table>
        </div>
    )
}
