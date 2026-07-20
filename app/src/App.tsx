// The app shell — routes the components M1/M2 built into a usable app
// (spec pre-003). Replaces the M0 health page.
import { Fragment, useEffect } from 'react'
import { Box, Button, Container, Stack, Typography } from '@mui/material'
import {
  BrowserRouter,
  Link as RouterLink,
  Navigate,
  Route,
  Routes,
  useLocation,
  useNavigate,
  useParams,
} from 'react-router-dom'
import { brandTint } from './theme'
import { AccessRequestQueue } from './components/AccessRequestQueue'
import { AdminQueue } from './components/AdminQueue'
import { BrowseListings } from './components/BrowseListings'
import { ChatWindow } from './components/ChatWindow'
import { ConversationList } from './components/ConversationList'
import { ListingDetail } from './components/ListingDetail'
import { ListingWizard } from './components/ListingWizard'
import { LoginForm } from './components/LoginForm'
import { MyListings } from './components/MyListings'
import { NavBar } from './components/NavBar'
import { RegisterForm } from './components/RegisterForm'
import { RequireAdmin } from './components/RequireAdmin'
import { RequireAuth } from './components/RequireAuth'
import { Wordmark } from './components/Wordmark'
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
//
// Signup is a dedicated full-page flow with its own header (back + wordmark)
// rather than the app nav: once someone has committed to signing up, the other
// nav actions are only distractions. The way back to login is the link under
// the submit button, not a corner button.
function RegisterRoute() {
  const navigate = useNavigate()
  const token = localStorage.getItem('token')
  if (token) {
    return <Navigate to="/my-listings" replace />
  }

  function handleBack() {
    // Deep-linked arrivals have nothing to go back to — fall back to home.
    if (window.history.length > 1) navigate(-1)
    else navigate('/')
  }

  return (
    <Box sx={{ minHeight: '100vh' }}>
      <Box
        component="header"
        sx={{
          display: 'grid',
          gridTemplateColumns: '1fr auto 1fr',
          alignItems: 'center',
          px: { xs: 2, sm: 3 },
          py: 2,
        }}
      >
        <Box sx={{ justifySelf: 'start' }}>
          <Button onClick={handleBack} sx={{ color: 'text.primary', fontWeight: 600, ml: -1 }}>
            <Box aria-hidden component="span" sx={{ mr: 0.75, fontSize: '1.1em', lineHeight: 1 }}>
              ←
            </Box>
            Back
          </Button>
        </Box>
        <Wordmark fontSize={28} />
        {/* Empty third column keeps the wordmark optically centered. */}
        <Box />
      </Box>

      <Container maxWidth="sm" sx={{ py: { xs: 3, sm: 5 } }}>
        <RegisterForm />
      </Container>
    </Box>
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
  // The public front door, in the succession voice (M4, spec 004 F7;
  // milestones.md § Scope fold-ins → M4). The positioning is *succession, not
  // transaction*: a business existed before the sale and continues after it,
  // and the seller chooses who carries it forward. That is not a slogan — it is
  // a plain description of `access_request` (requested → approved|denied), so
  // the promise and the architecture are the same sentence.
  //
  // The seller is the lead audience because supply is the scarce side, but a
  // seller-led framing leaves buyers cold, so the counter-story gets equal
  // billing rather than a footnote.
  const trustPoints = ['Curated listings', 'NDA-gated data rooms', 'Verified buyers']
  return (
    <Box
      sx={{
        minHeight: { xs: 'auto', md: 'calc(100vh - 65px)' },
        display: 'flex',
        alignItems: 'center',
        // Calm brand-blue wash at the top, fading into the app background.
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
              Succession, not transaction
            </Typography>
          </Box>

          <Typography
            variant="h2"
            component="h1"
            sx={{ fontSize: { xs: '2.15rem', sm: '2.75rem', md: '3.4rem' }, maxWidth: 780 }}
          >
            Every business deserves a next owner
          </Typography>

          <Typography
            variant="h6"
            component="p"
            sx={{ color: 'text.secondary', fontWeight: 400, maxWidth: 620 }}
          >
            You built it. You choose who carries it forward — and you decide who gets to look
            inside before they do.
          </Typography>

          {/* The buyer's half of the story. The seller-led framing above is
              deliberate (supply is the scarce side), but on its own it gives a
              buyer no reason to be here. */}
          <Typography
            variant="body1"
            sx={{ color: 'text.secondary', maxWidth: 560, pt: { xs: 0.5, md: 1 } }}
          >
            Buying? Take over something real — with customers, revenue and a history — instead of
            starting from zero.
          </Typography>

          {/* One CTA in the hero: the marketplace is the thing worth seeing
              first, and it is the only action the nav does not already carry
              (Log in and Get started live top-right, sticky, on every page). */}
          <Button component={RouterLink} to="/browse" variant="contained" size="large">
            Browse listings
          </Button>

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

// M5 — the seller's access-request queue for one listing (FR-14, spec 005 J4).
// The route guard is UX only; the real boundary is the server's
// `get_owned_listing` on the queue endpoint, which 404s a listing that is not
// yours (spec 005 D7/G2).
function ListingRequestsRoute() {
  const { id } = useParams()
  return (
    <>
      <Typography variant="h5" component="h1" gutterBottom>
        Access requests
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
        These buyers have asked to see this listing&apos;s private details. You choose who
        does.
      </Typography>
      <AccessRequestQueue listingId={Number(id)} />
    </>
  )
}

// M6 — chat: the conversation list is the one hub every conversation is
// reachable from this milestone (spec 006 § Decisions D5 — no per-listing
// deep link yet).
function ChatWindowRoute() {
  const { id } = useParams()
  return <ChatWindow conversationId={Number(id)} />
}

export function AppShell() {
  const navigate = useNavigate()
  const { pathname } = useLocation()
  // Signup owns its whole page, header included — the app nav would duplicate
  // the wordmark and add exits from a flow the visitor just chose to enter.
  const showNav = pathname !== '/register'

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
      {showNav && <NavBar />}
      <Routes>
        <Route path="/login" element={<LoginRoute />} />
        <Route path="/register" element={<RegisterRoute />} />
        <Route path="/" element={<LandingRoute />} />
        {/* M4 — public marketplace. Deliberately NOT wrapped in RequireAuth:
            browsing is the anonymous half of the trust gate (spec 004 F9). */}
        <Route path="/browse" element={<BrowseListings />} />
        <Route path="/browse/:id" element={<ListingDetail />} />
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
        <Route
          path="/admin"
          element={
            <RequireAdmin>
              <Container maxWidth="md" sx={{ mt: 4 }}>
                <AdminQueue />
              </Container>
            </RequireAdmin>
          }
        />
        {/* M5 — the seller decides who sees their data room (FR-14). Route-
            guarded by RequireAuth for UX only; the real boundary is the
            server's `get_owned_listing` on the queue endpoint, which 404s a
            listing that is not yours (spec 005 D7/G2). */}
        <Route
          path="/my-listings/:id/requests"
          element={
            <RequireAuth>
              <Container maxWidth="md" sx={{ mt: 4 }}>
                <ListingRequestsRoute />
              </Container>
            </RequireAuth>
          }
        />
        {/* M6 — realtime chat (FR-16). The conversation list + window; the
            server's require_conversation_member is the real boundary. */}
        <Route
          path="/messages"
          element={
            <RequireAuth>
              <Container maxWidth="md" sx={{ mt: 4 }}>
                <Typography variant="h5" component="h1" gutterBottom>
                  Messages
                </Typography>
                <ConversationList />
              </Container>
            </RequireAuth>
          }
        />
        <Route
          path="/messages/:id"
          element={
            <RequireAuth>
              <Container maxWidth="md" sx={{ mt: 4 }}>
                <ChatWindowRoute />
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
