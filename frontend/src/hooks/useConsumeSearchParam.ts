import { useEffect, useRef, useState } from 'react'
import { useLocation, useNavigate, useSearchParams } from 'react-router-dom'

/**
 * Read a deep-link search param once on mount, then strip it from the URL.
 *
 * Returns the param's value from the first render (or null). The param is removed with
 * `replace`, keeping other params and the hash, so it never lingers in the URL or history —
 * navigating to the same place manually never shows it.
 */
export function useConsumeSearchParam(name: string): string | null {
    const [searchParams] = useSearchParams()
    const location = useLocation()
    const navigate = useNavigate()
    const [value] = useState(() => searchParams.get(name))
    const hasConsumed = useRef(false)

    useEffect(() => {
        if (hasConsumed.current) return
        hasConsumed.current = true
        if (value === null) return

        // setSearchParams would drop the hash, which Home still needs to scroll to a section.
        const next = new URLSearchParams(location.search)
        next.delete(name)
        const search = next.toString()
        navigate({ search: search ? `?${search}` : '', hash: location.hash }, { replace: true })
        // Runs once on mount only — intentionally not reacting to later URL changes.
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [])

    return value
}
