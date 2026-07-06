import { afterEach } from "vitest"
import { cleanup } from "@testing-library/react"
import "@testing-library/jest-dom/vitest"

// Unmount components between tests — required since `globals: false` means
// @testing-library/react's automatic afterEach cleanup hook isn't wired up.
afterEach(() => {
    cleanup()
})
