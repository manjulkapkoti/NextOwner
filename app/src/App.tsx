// The app shell — routes the components M1/M2 built into a usable app
// (spec pre-003). Replaces the M0 health page.
import { Fragment, useEffect } from 'react'
import { Box, Button, Container, Stack, Typography } from '@mui/material'
import { BrowserRouter, Link, Navigate, Route, Routes, useNavigate } from 'react-router-dom'
import { brandTint } from './theme'
import { ListingWizard } from './components/ListingWizard'
import { LoginForm } from './components/LoginForm'
import { MyListings } from './components/MyListings'
import { NavBar } from './components/NavBar'
import { RegisterForm } from './components/RegisterForm'
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
    <Container
      maxWidth="sm"
      sx={{
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'center',
        minHeight: { xs: 'auto', sm: 'calc(100vh - 65px)' },
        py: { xs: 6, sm: 8 },
      }}
    >
      <LoginForm />
    </Container>
  )
}

// Public /register route — same already-authed treatment as /login (AS9):
// nothing useful to show a signed-in visitor here either.
function RegisterRoute() {
  const token = localStorage.getItem('token')
  if (token) {
    return <Navigate to="/my-listings" replace />
  }
  return (
    <Container
      maxWidth="sm"
      sx={{
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'center',
        minHeight: { xs: 'auto', sm: 'calc(100vh - 65px)' },
        py: { xs: 6, sm: 8 },
      }}
    >
      <RegisterForm />
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
  // The public front door. The real anonymous browse experience is M4; until
  // then this is a credibility-first hero, not a placeholder — brand, value
  // prop, and the two clear paths in (sign in / create an account).
  const trustPoints = ['Curated listings', 'NDA-gated data rooms', 'Verified buyers']
  return (
    <Box
      sx={{
        minHeight: { xs: 'auto', md: 'calc(100vh - 65px)' },
        display: 'flex',
        alignItems: 'center',
        // Calm indigo wash at the top, fading into the app background.
        background: `radial-gradient(1100px 520px at 50% -8%, ${brandTint}, transparent 62%)`,
      }}
    >
      <Container maxWidth="md" sx={{ py: { xs: 8, sm: 10, md: 12 }, textAlign: 'center' }}>
        <Stack spacing={{ xs: 3, md: 3.5 }} alignItems="center">
          <Box
            sx={{
              px: 1.5,
              py: 0.5,
              borderRadius: 999,
              bgcolor: 'background.paper',
              border: '1px solid',
              borderColor: 'divider',
              boxShadow: 1,
            }}
          >
            <Typography variant="caption" sx={{ color: 'primary.main', fontWeight: 600, letterSpacing: '0.02em' }}>
              The marketplace for online business acquisitions
            </Typography>
          </Box>

          <Typography
            variant="h2"
            component="h1"
            sx={{ fontSize: { xs: '2.15rem', sm: '2.75rem', md: '3.4rem' }, maxWidth: 780 }}
          >
            Buy and sell online businesses with confidence
          </Typography>

          <Typography
            variant="h6"
            component="p"
            sx={{ color: 'text.secondary', fontWeight: 400, maxWidth: 620 }}
          >
            The trusted marketplace for buying and selling small online businesses — vetted
            listings, gated data rooms, and verified buyers on both sides of the deal.
          </Typography>

          {/* Both ways in lead to /login: the login page is the only entrance
              to /register, so there is exactly one account-creation door
              rather than three. This CTA is not named "Log in" so it stays
              distinct from the nav's log-in link. */}
          <Box sx={{ width: { xs: '100%', sm: 'auto' }, pt: 1 }}>
            <Button
              variant="contained"
              size="large"
              component={Link}
              to="/login"
              sx={{ width: { xs: '100%', sm: 'auto' }, px: { sm: 4 } }}
            >
              Get started
            </Button>
          </Box>

          <Stack
            direction={{ xs: 'column', sm: 'row' }}
            spacing={{ xs: 0.75, sm: 1.75 }}
            alignItems="center"
            justifyContent="center"
            sx={{ pt: { xs: 2, md: 3 }, color: 'text.secondary' }}
          >
            {trustPoints.map((point, i) => (
              <Fragment key={point}>
                {i > 0 && (
                  <Box
                    sx={{ display: { xs: 'none', sm: 'block' }, width: 4, height: 4, borderRadius: '50%', bgcolor: 'text.disabled' }}
                  />
                )}
                <Typography variant="body2" sx={{ fontWeight: 500 }}>
                  {point}
                </Typography>
              </Fragment>
            ))}
          </Stack>
        </Stack>
      </Container>
    </Box>
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
        <Route path="/register" element={<RegisterRoute />} />
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
