import { StrictMode, Suspense, lazy } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Toaster } from 'sonner'
import './index.css'
import ErrorBoundary from './components/ErrorBoundary.tsx'
import Home from './pages/Home.tsx'
import Login from './pages/Login.tsx'
import { ThemeProvider } from "./components/theme-provider"
import DemoBanner from './components/DemoBanner.tsx'

const Learn = lazy(() => import('./pages/Learn.tsx'))
const ReactionLog = lazy(() => import('./pages/ReactionLog.tsx'))

const queryClient = new QueryClient()

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <ThemeProvider defaultTheme="system" storageKey="vite-ui-theme">
        <DemoBanner />
        <ErrorBoundary>
          <BrowserRouter basename="/rides-coordinator-bot">
            <Suspense fallback={<div className="min-h-screen flex items-center justify-center text-muted-foreground">Loading…</div>}>
              <Routes>
                <Route path="/login" element={<Login />} />
                <Route path="/" element={<Home />} />
                <Route path="/learn" element={<Learn />} />
                <Route path="/reaction-log" element={<ReactionLog />} />
              </Routes>
            </Suspense>
          </BrowserRouter>
        </ErrorBoundary>
        <Toaster position="bottom-right" richColors />
      </ThemeProvider>
    </QueryClientProvider>
  </StrictMode>,
)
