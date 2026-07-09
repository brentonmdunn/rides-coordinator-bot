import { act, renderHook, waitFor } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

vi.mock("@/lib/api", () => ({
  getApiUrl: (endpoint: string) => endpoint,
}))

// jsdom doesn't implement EventSource — stub it so the hook's SSE effect
// can mount/unmount without throwing, and so tests can drive onmessage /
// onerror manually. Mirrors the FakeEventSource pattern used in
// MessageTemplatesEditor.test.tsx.
class FakeEventSource {
  static instances: FakeEventSource[] = []
  onmessage: (() => void) | null = null
  onerror: (() => void) | null = null
  close = vi.fn()
  url: string

  constructor(url: string) {
    this.url = url
    FakeEventSource.instances.push(this)
  }
}
vi.stubGlobal("EventSource", FakeEventSource)

import { useReactionStream } from "./useReactionStream"

beforeEach(() => {
  FakeEventSource.instances = []
})

afterEach(() => {
  vi.useRealTimers()
  vi.clearAllMocks()
})

describe("useReactionStream", () => {
  it("shares a single EventSource across multiple subscribers and tears down when all unmount", () => {
    const onEventA = vi.fn()
    const onEventB = vi.fn()

    const hookA = renderHook(() => useReactionStream(onEventA))
    expect(FakeEventSource.instances).toHaveLength(1)

    const hookB = renderHook(() => useReactionStream(onEventB))
    // Still only one underlying connection.
    expect(FakeEventSource.instances).toHaveLength(1)
    expect(FakeEventSource.instances[0].close).not.toHaveBeenCalled()

    hookA.unmount()
    // One subscriber remains — stream stays open.
    expect(FakeEventSource.instances[0].close).not.toHaveBeenCalled()

    hookB.unmount()
    // Last subscriber gone — stream closes.
    expect(FakeEventSource.instances[0].close).toHaveBeenCalledTimes(1)
  })

  it("opens a fresh EventSource after a full teardown and remount", () => {
    const onEvent = vi.fn()

    const first = renderHook(() => useReactionStream(onEvent))
    expect(FakeEventSource.instances).toHaveLength(1)
    first.unmount()
    expect(FakeEventSource.instances[0].close).toHaveBeenCalledTimes(1)

    renderHook(() => useReactionStream(onEvent))
    expect(FakeEventSource.instances).toHaveLength(2)
    expect(FakeEventSource.instances[1].close).not.toHaveBeenCalled()
  })

  it("debounces a burst of onmessage events into one onEvent call per subscriber", () => {
    vi.useFakeTimers()
    const onEventA = vi.fn()
    const onEventB = vi.fn()

    renderHook(() => useReactionStream(onEventA))
    renderHook(() => useReactionStream(onEventB))

    const es = FakeEventSource.instances[0]
    act(() => {
      es.onmessage?.()
      es.onmessage?.()
      es.onmessage?.()
    })

    expect(onEventA).not.toHaveBeenCalled()
    expect(onEventB).not.toHaveBeenCalled()

    act(() => {
      vi.advanceTimersByTime(500)
    })

    expect(onEventA).toHaveBeenCalledTimes(1)
    expect(onEventB).toHaveBeenCalledTimes(1)
  })

  it("does not resubscribe when an inline onEvent callback changes identity across renders", () => {
    vi.useFakeTimers()
    let calls = 0
    const { rerender } = renderHook(({ cb }: { cb: () => void }) => useReactionStream(cb), {
      initialProps: { cb: () => (calls += 1) },
    })
    const firstInstanceCount = FakeEventSource.instances.length

    // Pass a brand-new inline arrow function — should not open a new stream.
    rerender({ cb: () => (calls += 1) })
    expect(FakeEventSource.instances).toHaveLength(firstInstanceCount)

    const es = FakeEventSource.instances[0]
    act(() => {
      es.onmessage?.()
      vi.advanceTimersByTime(500)
    })

    // The latest callback (from the rerender) is the one invoked.
    expect(calls).toBe(1)
  })

  it("sets streamError for all subscribers and closes the stream on error, without reconnecting", async () => {
    const onEventA = vi.fn()
    const onEventB = vi.fn()

    const hookA = renderHook(() => useReactionStream(onEventA))
    const hookB = renderHook(() => useReactionStream(onEventB))

    const es = FakeEventSource.instances[0]
    expect(hookA.result.current.streamError).toBe(false)
    expect(hookB.result.current.streamError).toBe(false)

    act(() => {
      es.onerror?.()
    })

    await waitFor(() => {
      expect(hookA.result.current.streamError).toBe(true)
      expect(hookB.result.current.streamError).toBe(true)
    })
    expect(es.close).toHaveBeenCalledTimes(1)
    expect(FakeEventSource.instances).toHaveLength(1)
  })
})
