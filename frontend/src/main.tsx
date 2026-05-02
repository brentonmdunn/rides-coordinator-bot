import { StrictMode, Suspense, lazy } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import './index.css'
import ErrorBoundary from './components/ErrorBoundary.tsx'
import AuthGuard from './components/AuthGuard.tsx'
import Home from './pages/Home.tsx'
import Login from './pages/Login.tsx'
import { ThemeProvider } from "./components/theme-provider"

const Learn = lazy(() => import('./pages/Learn.tsx'))

const queryClient = new QueryClient()

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <ThemeProvider defaultTheme="system" storageKey="vite-ui-theme">
        <ErrorBoundary>
          <BrowserRouter>
            <Suspense fallback={<div className="min-h-screen flex items-center justify-center text-slate-500">Loading…</div>}>
              <Routes>
                <Route path="/login" element={<Login />} />
                <Route element={<AuthGuard />}>
                  <Route path="/" element={<Home />} />
                  <Route path="/learn" element={<Learn />} />
                </Route>
              </Routes>
            </Suspense>
          </BrowserRouter>
        </ErrorBoundary>
      </ThemeProvider>
    </QueryClientProvider>
  </StrictMode>,
)
