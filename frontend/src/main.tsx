import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import './index.css'
import ErrorBoundary from './components/ErrorBoundary.tsx'
import Home from './pages/Home.tsx'
import Learn from './pages/Learn.tsx'
import { ThemeProvider } from "./components/theme-provider"

const queryClient = new QueryClient()

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <ThemeProvider defaultTheme="system" storageKey="vite-ui-theme">
        <ErrorBoundary>
          <BrowserRouter>
            <Routes>
              <Route path="/" element={<Home />} />
              <Route path="/learn" element={<Learn />} />
            </Routes>
          </BrowserRouter>
        </ErrorBoundary>
      </ThemeProvider>
    </QueryClientProvider>
  </StrictMode>,
)
