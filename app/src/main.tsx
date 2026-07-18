import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { CssBaseline, ThemeProvider } from '@mui/material'
// Self-hosted (@fontsource) — no external font request, so it's CSP-safe and
// works offline. Inter carries the UI, Manrope the display headings (h1-h4),
// per docs/design_tokens_v1.md § typography.
import '@fontsource/inter/400.css'
import '@fontsource/inter/500.css'
import '@fontsource/inter/600.css'
import '@fontsource/inter/700.css'
import '@fontsource/manrope/600.css'
import '@fontsource/manrope/700.css'
import App from './App.tsx'
import { ErrorBoundary } from './components/ErrorBoundary'
import { theme } from './theme'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ThemeProvider theme={theme}>
      {/* CssBaseline picks up the theme's background + typography */}
      <CssBaseline />
      <ErrorBoundary>
        <App />
      </ErrorBoundary>
    </ThemeProvider>
  </StrictMode>,
)
