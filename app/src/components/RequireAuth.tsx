// Route guard — redirects a logged-out visitor to /login (spec H1).
// This is UX ONLY. The server permission gate is the real boundary; hiding a
// route never protects data (security.md §Frontend session). It reads the token
// straight from localStorage — the single source of truth for "is a session
// present" — so it reacts to login/logout without extra wiring.
import type { ReactNode } from 'react'
import { Navigate } from 'react-router-dom'

export function RequireAuth({ children }: { children: ReactNode }) {
  const token = localStorage.getItem('token')
  if (!token) {
    return <Navigate to="/login" replace />
  }
  return <>{children}</>
}
