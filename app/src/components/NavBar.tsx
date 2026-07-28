// Top nav — brand + auth-aware actions on the right (spec AS5).
// Auth-aware via authStore (MobX observer) so it re-renders on login/logout.
// This is chrome, not a security boundary — RequireAuth + the server gates
// the actual routes and data.
//
// Layout (design_system_spec.md): actions sit top-right at every width.
//  - Logged out: "Log in" + "Get started" — the log-in affordance lives here,
//    not in the landing hero, so it is in the same place on every page.
//  - Logged in: UI Pass 2 consolidated 7 inline controls down to 4 + a right
//    cluster (bell / envelope / avatar), because a phone-width nav with seven
//    labelled controls is what collapses to a menu in the first place; the
//    consolidation is what let a *desktop* nav stay legible too. Below `sm`
//    everything (the 4 + the right cluster's destinations) still collapses
//    into the one hamburger menu.
//
// The breakpoint is CSS (`display`), not a JS media query: both branches stay
// in the DOM so tests (and any non-matchMedia environment) see the inline row,
// while the closed Menu/Popover renders nothing — so a label is never
// ambiguous between the desktop and mobile copies.
import { useEffect, useState, type MouseEvent } from 'react'
import {
  AppBar,
  Avatar,
  Badge,
  Box,
  Button,
  Container,
  IconButton,
  Menu,
  MenuItem,
  Stack,
  Toolbar,
} from '@mui/material'
import type { SxProps, Theme } from '@mui/material/styles'
import { observer } from 'mobx-react-lite'
import { Link as RouterLink, useLocation, useNavigate } from 'react-router-dom'
import MailOutlineIcon from '@mui/icons-material/MailOutline'
import NotificationsOutlinedIcon from '@mui/icons-material/NotificationsOutlined'
import { brandTint } from '../theme'
import { authStore, type CurrentUser } from '../stores/authStore'
import { chatStore } from '../stores/chatStore'
import { notificationStore } from '../stores/notificationStore'
import { verificationStore } from '../stores/verificationStore'
import { watchlistStore } from '../stores/watchlistStore'
import { Wordmark } from './Wordmark'

// Three stacked bars — a hamburger without pulling in an icon package for one
// glyph. aria-hidden because the IconButton itself carries the accessible name.
function MenuGlyph() {
  return (
    <Box aria-hidden sx={{ display: 'grid', gap: '4px', width: 18 }}>
      {[0, 1, 2].map((i) => (
        <Box key={i} sx={{ height: 2, borderRadius: 1, bgcolor: 'currentColor' }} />
      ))}
    </Box>
  )
}

// The account avatar's initial. `authStore.user` is only populated after
// `loadUser()` resolves (login, or the effect below on a fresh page load with
// an existing token) — "?" is the honest placeholder for the gap between "has
// a token" and "know who they are".
function initialFor(user: CurrentUser | null): string {
  const source = user?.display_name?.trim() || user?.email
  return source ? source.charAt(0).toUpperCase() : '?'
}

export const NavBar = observer(function NavBar() {
  const navigate = useNavigate()
  const { pathname } = useLocation()
  const [anchorEl, setAnchorEl] = useState<HTMLElement | null>(null)
  const [accountAnchorEl, setAccountAnchorEl] = useState<HTMLElement | null>(null)
  const menuOpen = Boolean(anchorEl)
  const accountMenuOpen = Boolean(accountAnchorEl)

  // M6 — the unread badge (spec 006 J1). Refetched on route change: the same
  // "poll/refetch on route change, fine for MVP" pattern the rest of the app
  // already uses (design_implementation.md — no new live-update mechanism
  // needed just for a nav badge).
  useEffect(() => {
    // Best-effort: a failed badge refresh is not worth surfacing to the
    // user (or, in tests that don't stub fetch, worth an unhandled
    // rejection) — the nav chrome degrades to "no badge", not an error.
    if (authStore.isAuthenticated) {
      chatStore.loadConversations().catch(() => {})
      notificationStore.loadUnreadCount().catch(() => {})
    }
  }, [pathname])

  // UI Pass 2 — the avatar needs the current user's name/email for its
  // initial; nothing before this pass loaded it outside of login and the
  // admin route guard, so a reload elsewhere left it permanently unknown.
  useEffect(() => {
    if (authStore.isAuthenticated && !authStore.user) {
      authStore.loadUser().catch(() => {})
    }
  }, [])

  const unreadTotal = chatStore.conversations.reduce((sum, c) => sum + c.unread_count, 0)

  function isActive(path: string): boolean {
    return pathname === path || pathname.startsWith(`${path}/`)
  }

  // Active-route indication (design_system_spec.md §5 "Navigation — active
  // item in blue"): the matching nav button gets a brand-tint pill rather than
  // just a colour change, so it reads at a glance rather than on close look.
  function navSx(path: string): SxProps<Theme> {
    return isActive(path)
      ? { color: 'text.primary', fontWeight: 600, bgcolor: brandTint, borderRadius: 999 }
      : { color: 'text.secondary' }
  }

  function handleLogout() {
    setAnchorEl(null)
    setAccountAnchorEl(null)
    authStore.logout()
    // M9 — a second user logging in on the same session must not inherit the
    // first user's watchlist state.
    watchlistStore.reset()
    // M10 — same reasoning for verification state.
    verificationStore.reset()
    navigate('/login')
  }

  function go(path: string) {
    setAnchorEl(null)
    setAccountAnchorEl(null)
    navigate(path)
  }

  return (
    <AppBar position="sticky">
      <Container maxWidth="lg">
        <Toolbar disableGutters sx={{ minHeight: 68, gap: 1 }}>
          {/* Brand — also the way home from anywhere in the app. */}
          <Stack
            component={RouterLink}
            to="/"
            direction="row"
            alignItems="center"
            spacing={1}
            sx={{
              flexGrow: 1,
              minWidth: 0,
              textDecoration: 'none',
              color: 'inherit',
            }}
          >
            {/* Wordmark on wide screens, the tile alone below sm (768px).
                At 360px the bar has ~328px, and the two auth buttons take
                ~176px of it — not enough for 30px of wordmark, but ample for
                a 30px tile. They are never both shown, so the ring cannot
                appear twice. */}
            <Box sx={{ display: { xs: 'none', sm: 'block' } }}>
              <Wordmark fontSize={30} />
            </Box>
            <Box sx={{ display: { xs: 'block', sm: 'none' } }}>
              <Wordmark iconSize={30} iconOnly />
            </Box>
          </Stack>

          {/* M4 — the public marketplace, reachable from every page whether or
              not there is a session. The label stays literal: the succession
              voice lives in headlines and prose, never in navigation, because a
              label someone has to decode trades usability for poetry
              (milestones.md § Scope fold-ins → M4). */}
          <Button
            color="inherit"
            component={RouterLink}
            to="/browse"
            sx={{ whiteSpace: 'nowrap', ...navSx('/browse') }}
          >
            Browse
          </Button>

          {/* M11 — the valuation calculator (spec 011 U8). Beside Browse, in the
              always-visible row rather than the account menu: it is a lead
              magnet aimed at people who have never signed up, so a link that
              only appears once you have an account is the one placement that
              defeats its purpose. Hidden below `sm` — the two supply-side and
              demand-side entry points compete for the same narrow strip, and
              Browse wins it. */}
          <Button
            color="inherit"
            component={RouterLink}
            to="/valuation"
            sx={{
              whiteSpace: 'nowrap',
              display: { xs: 'none', sm: 'inline-flex' },
              ...navSx('/valuation'),
            }}
          >
            Valuation
          </Button>

          {authStore.isAuthenticated ? (
            <>
              {/* >=sm: 4 inline controls + the bell/envelope/avatar cluster. */}
              <Stack
                direction="row"
                spacing={0.5}
                alignItems="center"
                sx={{
                  display: { xs: 'none', sm: 'flex' },
                  '& .MuiButton-root': { whiteSpace: 'nowrap' },
                }}
              >
                <Button variant="contained" onClick={() => go('/sell')}>
                  List a business
                </Button>
                <Button color="inherit" onClick={() => go('/my-listings')} sx={navSx('/my-listings')}>
                  My listings
                </Button>
                {/* M7 — offers/LOI (FR-17): the buyer's cross-listing thread
                    history, the same "one hub" shape /messages already is. */}
                <Button color="inherit" onClick={() => go('/my-offers')} sx={navSx('/my-offers')}>
                  My offers
                </Button>
              </Stack>

              <Stack
                direction="row"
                spacing={0.5}
                alignItems="center"
                sx={{ display: { xs: 'none', sm: 'flex' } }}
              >
                <IconButton
                  aria-label="Notifications"
                  component={RouterLink}
                  to="/notifications"
                  sx={{ color: 'text.secondary' }}
                >
                  <Badge badgeContent={notificationStore.unreadCount} color="primary">
                    <NotificationsOutlinedIcon />
                  </Badge>
                </IconButton>
                <IconButton
                  aria-label="Messages"
                  component={RouterLink}
                  to="/messages"
                  sx={{ color: 'text.secondary' }}
                >
                  <Badge badgeContent={unreadTotal} color="primary">
                    <MailOutlineIcon />
                  </Badge>
                </IconButton>
                <IconButton
                  aria-label="Account menu"
                  aria-haspopup="true"
                  aria-expanded={accountMenuOpen || undefined}
                  onClick={(e: MouseEvent<HTMLElement>) => setAccountAnchorEl(e.currentTarget)}
                  size="small"
                  sx={{ ml: 0.5 }}
                >
                  <Avatar sx={{ width: 32, height: 32, bgcolor: 'primary.main', fontSize: '0.9rem' }}>
                    {initialFor(authStore.user)}
                  </Avatar>
                </IconButton>
                <Menu
                  anchorEl={accountAnchorEl}
                  open={accountMenuOpen}
                  onClose={() => setAccountAnchorEl(null)}
                  anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
                  transformOrigin={{ vertical: 'top', horizontal: 'right' }}
                  slotProps={{ paper: { sx: { minWidth: 180, mt: 1 } } }}
                >
                  <MenuItem onClick={() => go('/watchlist')}>Watchlist</MenuItem>
                  <MenuItem onClick={() => go('/saved-searches')}>Saved searches</MenuItem>
                  {/* M10 — buyer verification (spec 010, D4: no role gate, any
                      authenticated user may submit). */}
                  <MenuItem onClick={() => go('/verification')}>Verification</MenuItem>
                  {/* MUI's Menu clones its children directly and warns against
                      a Fragment child ("doesn't accept a Fragment as a
                      child... provide an array instead") — an array with keys
                      is what it actually wants here. */}
                  {authStore.user?.is_admin && [
                    <MenuItem key="curation" onClick={() => go('/admin')}>
                      Curation queue
                    </MenuItem>,
                    <MenuItem key="verifications" onClick={() => go('/admin/verifications')}>
                      Verifications
                    </MenuItem>,
                  ]}
                  <MenuItem onClick={handleLogout}>Logout</MenuItem>
                </Menu>
              </Stack>

              {/* <sm: one control instead of everything above. */}
              <IconButton
                aria-label="Open menu"
                aria-haspopup="true"
                aria-expanded={menuOpen || undefined}
                onClick={(e: MouseEvent<HTMLElement>) => setAnchorEl(e.currentTarget)}
                sx={{ display: { xs: 'inline-flex', sm: 'none' }, color: 'text.secondary' }}
              >
                <MenuGlyph />
              </IconButton>
              <Menu
                anchorEl={anchorEl}
                open={menuOpen}
                onClose={() => setAnchorEl(null)}
                anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
                transformOrigin={{ vertical: 'top', horizontal: 'right' }}
                slotProps={{ paper: { sx: { minWidth: 200, mt: 1 } } }}
              >
                <MenuItem onClick={() => go('/sell')}>List a business</MenuItem>
                <MenuItem onClick={() => go('/my-listings')}>My listings</MenuItem>
                <MenuItem onClick={() => go('/my-offers')}>My offers</MenuItem>
                <MenuItem onClick={() => go('/watchlist')}>Watchlist</MenuItem>
                <MenuItem onClick={() => go('/saved-searches')}>Saved searches</MenuItem>
                {/* M10 — buyer verification (spec 010, D4: no role gate, any
                    authenticated user may submit). */}
                <MenuItem onClick={() => go('/verification')}>Verification</MenuItem>
                <MenuItem onClick={() => go('/notifications')}>
                  Notifications{notificationStore.unreadCount > 0 ? ` (${notificationStore.unreadCount})` : ''}
                </MenuItem>
                <MenuItem onClick={() => go('/messages')}>
                  Messages{unreadTotal > 0 ? ` (${unreadTotal})` : ''}
                </MenuItem>
                {authStore.user?.is_admin && [
                  <MenuItem key="curation" onClick={() => go('/admin')}>
                    Curation queue
                  </MenuItem>,
                  <MenuItem key="verifications" onClick={() => go('/admin/verifications')}>
                    Verifications
                  </MenuItem>,
                ]}
                <MenuItem onClick={handleLogout}>Logout</MenuItem>
              </Menu>
            </>
          ) : (
            /* Logged out: returning visitor (Log in) and new visitor (Get
               started) each get their own action, top-right on every page.
               Two short labels — these fit at 320px, so no collapse needed. */
            <Stack
              direction="row"
              spacing={{ xs: 0.5, sm: 1 }}
              alignItems="center"
              sx={{ '& .MuiButton-root': { whiteSpace: 'nowrap' } }}
            >
              <Button color="inherit" component={RouterLink} to="/login" sx={{ color: 'text.secondary' }}>
                Log in
              </Button>
              <Button variant="contained" component={RouterLink} to="/register">
                Get started
              </Button>
            </Stack>
          )}
        </Toolbar>
      </Container>
    </AppBar>
  )
})
