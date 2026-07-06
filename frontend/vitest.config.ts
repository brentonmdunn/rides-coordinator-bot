import path from "path"
import react from "@vitejs/plugin-react"
import { defineConfig } from "vitest/config"

// Separate from vite.config.ts so the production build config stays
// untouched by test-only concerns (jsdom environment, setup files).
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    globals: false,
  },
})
