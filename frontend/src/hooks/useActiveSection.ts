import { useEffect, useRef, useState } from 'react'

export function useActiveSection(ids: string[]): string {
    const [activeId, setActiveId] = useState(ids[0] ?? '')
    const observerRef = useRef<IntersectionObserver | null>(null)
    const idsKey = ids.join(',')

    useEffect(() => {
        observerRef.current?.disconnect()

        const observer = new IntersectionObserver(
            (entries) => {
                for (const entry of entries) {
                    if (entry.isIntersecting) {
                        setActiveId(entry.target.id)
                        break
                    }
                }
            },
            { rootMargin: '-10% 0px -80% 0px', threshold: 0 }
        )

        observerRef.current = observer

        for (const id of idsKey.split(',')) {
            const el = document.getElementById(id)
            if (el) observer.observe(el)
        }

        return () => observer.disconnect()
    }, [idsKey])

    return activeId
}
