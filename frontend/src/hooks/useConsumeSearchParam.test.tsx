import { render, screen, waitFor } from "@testing-library/react"
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom"
import { describe, expect, it } from "vitest"
import { useConsumeSearchParam } from "./useConsumeSearchParam"

function Probe() {
    const value = useConsumeSearchParam("settings")
    const location = useLocation()
    return (
        <>
            <p data-testid="value">{value ?? "null"}</p>
            <p data-testid="search">{location.search}</p>
            <p data-testid="hash">{location.hash}</p>
        </>
    )
}

function renderAt(initialPath: string) {
    render(
        <MemoryRouter initialEntries={[initialPath]}>
            <Routes>
                <Route path="/" element={<Probe />} />
            </Routes>
        </MemoryRouter>,
    )
}

const text = (id: string) => screen.getByTestId(id).textContent

describe("useConsumeSearchParam", () => {
    it("returns the value and strips only that param, keeping other params and the hash", async () => {
        renderAt("/?settings=pickup-summaries&foo=bar#reactions")

        await waitFor(() => expect(text("search")).toBe("?foo=bar"))
        expect(text("value")).toBe("pickup-summaries")
        expect(text("hash")).toBe("#reactions")
    })

    it("keeps returning the first value after the param is stripped", async () => {
        renderAt("/?settings=pickup-summaries")

        await waitFor(() => expect(text("search")).toBe(""))
        expect(text("value")).toBe("pickup-summaries")
    })

    it("returns null and leaves the URL alone when the param is absent", async () => {
        renderAt("/?foo=bar#x")

        expect(text("value")).toBe("null")
        await waitFor(() => expect(text("search")).toBe("?foo=bar"))
        expect(text("hash")).toBe("#x")
    })
})
