// The app shell — routes the components M1/M2 built into a usable app
// (spec pre-003). Replaces the M0 health page.
import { useEffect } from 'react'
import { Box, Button, Container, Typography } from '@mui/material'
import {
  BrowserRouter,
  Navigate,
  Route,
  Routes,
  useLocation,
  useNavigate,
  useParams,
} from 'react-router-dom'
import { AccessRequestQueue } from './components/AccessRequestQueue'
import { AdminQueue } from './components/AdminQueue'
import { BrowseListings } from './components/BrowseListings'
import { ChatWindow } from './components/ChatWindow'
import { ConversationList } from './components/ConversationList'
import { LandingPage } from './components/LandingPage'
import { ListingDetail } from './components/ListingDetail'
import { ListingOffersQueue } from './components/ListingOffersQueue'
import { ListingWizard } from './components/ListingWizard'
import { LoginForm } from './components/LoginForm'
import { MyListings } from './components/MyListings'
import { MyOffers } from './components/MyOffers'
import { NavBar } from './components/NavBar'
import { NotificationInbox } from './components/NotificationInbox'
import { SavedSearches } from './components/SavedSearches'
import { Watchlist } from './components/Watchlist'
import { ForgotPasswordPage } from './components/ForgotPasswordPage'
import { ResetPasswordPage } from './components/ResetPasswordPage'
import { VerifyEmailPage } from './components/VerifyEmailPage'
import { RegisterForm } from './components/RegisterForm'
import { RequireAdmin } from './components/RequireAdmin'
import { RequireAuth } from './components/RequireAuth'
import { Wordmark } from './components/Wordmark'
import { authStore } from './stores/authStore'
import { watchlistStore } from './stores/watchlistStore'

// M8 — the three account-recovery pages (spec 008 J8-J10). Public by design:
// the whole audience for "reset my password" is people without a session.
function ForgotPasswordRoute() {
  return (
    <Container maxWidth="sm" sx={{ mt: 6 }}>
      <ForgotPasswordPage />
    </Container>
  )
}

function ResetPasswordRoute() {
  return (
    <Container maxWidth="sm" sx={{ mt: 6 }}>
      <ResetPasswordPage />
    </Container>
  )
}

function VerifyEmailRoute() {
  return (
    <Container maxWidth="sm" sx={{ mt: 6 }}>
      <VerifyEmailPage />
    </Container>
  )
}

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
  //
  // UI Pass 2: the markup lives in `LandingPage.tsx` now (the "first
  // impression" pass restyled it); this route's only job is the
  // already-authed redirect above.
  return <LandingPage />
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

// M7 — the seller's per-listing offers queue (spec 007 J3, FR-17). Route-
// guarded by RequireAuth for UX only; the real boundary is the server's
// `get_owned_listing` on the queue endpoint, which 404s a listing that is not
// yours (spec 007 G2, mirroring spec 005's ListingRequestsRoute above).
function ListingOffersRoute() {
  const { id } = useParams()
  return (
    <>
      <Typography variant="h5" component="h1" gutterBottom>
        Offers
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
        Every buyer&apos;s negotiation on this listing, oldest first. Accepting one
        automatically declines every other pending offer.
      </Typography>
      <ListingOffersQueue listingId={Number(id)} />
    </>
  )
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
      // M9 — a second user logging in on the same session must not inherit
      // the first user's watchlist state (mirrors the client-state-is-
      // convenience-only rule other stores follow at logout/session-death).
      watchlistStore.reset()
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
        {/* M8 — account recovery. Deliberately NOT behind RequireAuth: a user
            who cannot log in is the entire audience for these three pages
            (spec 008 G, H). The server gates them with a one-time token, not
            with a session. */}
        <Route path="/forgot-password" element={<ForgotPasswordRoute />} />
        <Route path="/reset-password" element={<ResetPasswordRoute />} />
        <Route path="/verify-email" element={<VerifyEmailRoute />} />
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
        {/* M8 — the inbox and saved searches (FR-22, FR-11). */}
        <Route
          path="/notifications"
          element={
            <RequireAuth>
              <Container maxWidth="md" sx={{ mt: 4 }}>
                <Typography variant="h5" gutterBottom>
                  Notifications
                </Typography>
                <NotificationInbox />
              </Container>
            </RequireAuth>
          }
        />
        <Route
          path="/saved-searches"
          element={
            <RequireAuth>
              <Container maxWidth="md" sx={{ mt: 4 }}>
                <Typography variant="h5" gutterBottom>
                  Saved searches
                </Typography>
                <SavedSearches />
              </Container>
            </RequireAuth>
          }
        />
        {/* M9 — the watchlist (spec 009, FR-12). */}
        <Route
          path="/watchlist"
          element={
            <RequireAuth>
              <Container maxWidth="md" sx={{ mt: 4 }}>
                <Typography variant="h5" gutterBottom>
                  Watchlist
                </Typography>
                <Watchlist />
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
        {/* M7 — offers/LOI (FR-17). The buyer's cross-listing dashboard, and
            the seller's per-listing queue; the offer panel itself lives on
            /browse/:id (ListingDetail), gated the same way the data room is. */}
        <Route
          path="/my-offers"
          element={
            <RequireAuth>
              <Container maxWidth="md" sx={{ mt: 4 }}>
                <Typography variant="h5" component="h1" gutterBottom>
                  Your offers
                </Typography>
                <MyOffers />
              </Container>
            </RequireAuth>
          }
        />
        <Route
          path="/my-listings/:id/offers"
          element={
            <RequireAuth>
              <Container maxWidth="md" sx={{ mt: 4 }}>
                <ListingOffersRoute />
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
