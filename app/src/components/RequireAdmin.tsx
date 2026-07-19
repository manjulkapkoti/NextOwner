// Route guard for admin-only screens (spec F2).
//
// UX ONLY, and more visibly so than RequireAuth: hiding the queue protects
// nothing, because the data lives behind `require_admin` on the server, which
// re-reads is_admin from the DB on every request (spec A3/A4). This exists so a
// non-admin is not shown a broken screen full of 403s — not to keep them out.
//
// It waits for the user to load before deciding. Redirecting while `user` is
// still null would bounce a legitimate admin on every hard refresh, since the
// token is in localStorage but the profile has not been fetched yet.
import { useEffect, type ReactNode } from 'react'
import { CircularProgress, Stack } from '@mui/material'
import { observer } from 'mobx-react-lite'
import { Navigate } from 'react-router-dom'
import { authStore } from '../stores/authStore'

export const RequireAdmin = observer(function RequireAdmin({ children }: { children: ReactNode }) {
  const token = localStorage.getItem('token')

  useEffect(() => {
    if (token && !authStore.user) {
      void authStore.loadUser()
    }
  }, [token])

  if (!token) {
    return <Navigate to="/login" replace />
  }
  if (!authStore.user) {
    return (
      <Stack alignItems="center" sx={{ py: 8 }}>
        <CircularProgress aria-label="checking permissions" />
      </Stack>
    )
  }
  if (!authStore.user.is_admin) {
    return <Navigate to="/my-listings" replace />
  }
  return <>{children}</>
})
