// The app shell — routes the components M1/M2 built into a usable app
// (spec pre-003). Replaces the M0 health page.
import { useEffect } from 'react'
import { Button, Container, Typography } from '@mui/material'
import { BrowserRouter, Link, Navigate, Route, Routes, useNavigate } from 'react-router-dom'
import { ListingWizard } from './components/ListingWizard'
import { LoginForm } from './components/LoginForm'
import { MyListings } from './components/MyListings'
import { NavBar } from './components/NavBar'
import { RequireAuth } from './components/RequireAuth'
import { authStore } from './stores/authStore'

// Public /login route: if a session already exists, skip the form (AS3) —
// there is nothing useful to show an already-signed-in visitor here.
function LoginRoute() {
  const token = localStorage.getItem('token')
  if (token) {
    return <Navigate to="/my-listings" replace />
  }
  return (
    <Container maxWidth="sm" sx={{ mt: 8 }}>
      <LoginForm />
    </Container>
  )
}

// The landing route (/): an authed visitor is sent straight to their
// dashboard (AS6, unchanged). A logged-out visitor gets a minimal public
// placeholder instead of an unexplained bounce to the login form (AS7) —
// the real anonymous browse experience is M4; this is a stopgap until then.
function LandingRoute() {
  const token = localStorage.getItem('token')
  if (token) {
    return <Navigate to="/my-listings" replace />
  }
  return (
    <Container maxWidth="sm" sx={{ mt: 12, textAlign: 'center' }}>
      <Typography variant="h3" gutterBottom>
        NextOwner
      </Typography>
      <Typography variant="h6" color="text.secondary" gutterBottom>
        A marketplace for buying and selling small online businesses.
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 4 }}>
        The public listings page is coming soon — sign in to get started.
      </Typography>
      <Button variant="contained" component={Link} to="/login">
        Log in
      </Button>
    </Container>
  )
}

export function AppShell() {
  const navigate = useNavigate()

  // Global 401 handling (plan slice 2): api.ts emits this on ANY 401, so a
  // stale/expired token anywhere in the app sends the user back to login
  // instead of leaving them stuck on a dead page (AS4).
  useEffect(() => {
    function onUnauthorized() {
      authStore.logout()
      navigate('/login')
    }
    window.addEventListener('auth:unauthorized', onUnauthorized)
    return () => window.removeEventListener('auth:unauthorized', onUnauthorized)
  }, [navigate])

  return (
    <>
      <NavBar />
      <Routes>
        <Route path="/login" element={<LoginRoute />} />
        <Route path="/" element={<LandingRoute />} />
        <Route
          path="/my-listings"
          element={
            <RequireAuth>
              <Container maxWidth="md" sx={{ mt: 4 }}>
                <MyListings />
              </Container>
            </RequireAuth>
          }
        />
        <Route
          path="/sell"
          element={
            <RequireAuth>
              <Container maxWidth="md" sx={{ mt: 4 }}>
                <ListingWizard />
              </Container>
            </RequireAuth>
          }
        />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <AppShell />
    </BrowserRouter>
  )
}
