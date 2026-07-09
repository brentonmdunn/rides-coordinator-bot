import { useEffect, useRef, useState } from 'react'
import { getApiUrl } from '../lib/api'

const DEBOUNCE_MS = 500

interface StreamState {
    eventSource: EventSource
    debounceTimer: ReturnType<typeof setTimeout> | null
    subscribers: Set<() => void>
    errorSetters: Set<(error: boolean) => void>
}

let state: StreamState | null = null

function notifySubscribers(): void {
    if (!state) return
    for (const notify of state.subscribers) {
        notify()
    }
}

function handleMessage(): void {
    if (!state) return
    if (state.debounceTimer !== null) {
        clearTimeout(state.debounceTimer)
    }
    state.debounceTimer = setTimeout(() => {
        if (!state) return
        state.debounceTimer = null
        notifySubscribers()
    }, DEBOUNCE_MS)
}

function handleError(): void {
    if (!state) return
    for (const setError of state.errorSetters) {
        setError(true)
    }
    teardown()
}

function teardown(): void {
    if (!state) return
    if (state.debounceTimer !== null) {
        clearTimeout(state.debounceTimer)
    }
    state.eventSource.close()
    state = null
}

function ensureStream(): StreamState {
    if (!state) {
        const eventSource = new EventSource(getApiUrl('/api/reaction-log/stream'), {
            withCredentials: true,
        })
        state = {
            eventSource,
            debounceTimer: null,
            subscribers: new Set(),
            errorSetters: new Set(),
        }
        eventSource.onmessage = handleMessage
        eventSource.onerror = handleError
    }
    return state
}

/**
 * Shared SSE subscription to the reaction-log live stream.
 *
 * The first mounted caller opens the underlying EventSource; later callers
 * reuse it. When the last caller unmounts, the stream closes so a future
 * mount reopens a fresh connection. Incoming messages are debounced
 * (trailing edge, {@link DEBOUNCE_MS}) so a burst of reaction events
 * collapses into a single `onEvent` call per subscriber.
 */
export function useReactionStream(onEvent: () => void): { streamError: boolean } {
    const [streamError, setStreamError] = useState(false)
    const onEventRef = useRef(onEvent)

    useEffect(() => {
        onEventRef.current = onEvent
    }, [onEvent])

    useEffect(() => {
        const s = ensureStream()

        const notify = (): void => onEventRef.current()
        const setError = (error: boolean): void => setStreamError(error)

        s.subscribers.add(notify)
        s.errorSetters.add(setError)

        return () => {
            if (!state) return
            state.subscribers.delete(notify)
            state.errorSetters.delete(setError)
            if (state.subscribers.size === 0) {
                teardown()
            }
        }
    }, [])

    return { streamError }
}
