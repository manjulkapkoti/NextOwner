// Top nav — brand + auth-aware actions on the right (spec AS5).
// Auth-aware via authStore (MobX observer) so it re-renders on login/logout.
// This is chrome, not a security boundary — RequireAuth + the server gates
// the actual routes and data.
//
// Layout (design_system_spec.md): actions sit top-right at every width.
//  - Logged out: "Log in" + "Get started" — the log-in affordance lives here,
//    not in the landing hero, so it is in the same place on every page.
//  - Logged in:  the three actions inline on >=sm; below sm they collapse into
//    a menu, because three labelled buttons plus the brand wrap on a phone.
//
// The breakpoint is CSS (`display`), not a JS media query: both branches stay
// in the DOM so tests (and any non-matchMedia environment) see the inline row,
// while the closed Menu renders nothing — so "Logout" is never ambiguous.
import { useEffect, useState, type MouseEvent } from 'react'
import {
  AppBar,
  Box,
  Button,
  Container,
  IconButton,
  Menu,
  MenuItem,
  Stack,
  Toolbar,
} from '@mui/material'
import { observer } from 'mobx-react-lite'
import { Link as RouterLink, useLocation, useNavigate } from 'react-router-dom'
import { authStore } from '../stores/authStore'
import { chatStore } from '../stores/chatStore'
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

export const NavBar = observer(function NavBar() {
  const navigate = useNavigate()
  const { pathname } = useLocation()
  const [anchorEl, setAnchorEl] = useState<HTMLElement | null>(null)
  const menuOpen = Boolean(anchorEl)

  // M6 — the unread badge (spec 006 J1). Refetched on route change: the same
  // "poll/refetch on route change, fine for MVP" pattern the rest of the app
  // already uses (design_implementation.md — no new live-update mechanism
  // needed just for a nav badge).
  useEffect(() => {
    // Best-effort: a failed badge refresh is not worth surfacing to the
    // user (or, in tests that don't stub fetch, worth an unhandled
    // rejection) — the nav chrome degrades to "no badge", not an error.
    if (authStore.isAuthenticated) chatStore.loadConversations().catch(() => {})
  }, [pathname])
  const unreadTotal = chatStore.conversations.reduce((sum, c) => sum + c.unread_count, 0)

  function handleLogout() {
    setAnchorEl(null)
    authStore.logout()
    navigate('/login')
  }

  function go(path: string) {
    setAnchorEl(null)
    navigate(path)
  }

  return (
    <AppBar position="sticky">
      <Container maxWidth="lg">
        <Toolbar disableGutters sx={{ minHeight: 64, gap: 1 }}>
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
            sx={{ color: 'text.secondary', whiteSpace: 'nowrap' }}
          >
            Browse
          </Button>

          {authStore.isAuthenticated ? (
            <>
              {/* >=sm: the actions inline. */}
              <Stack
                direction="row"
                spacing={1}
                alignItems="center"
                sx={{
                  display: { xs: 'none', sm: 'flex' },
                  '& .MuiButton-root': { whiteSpace: 'nowrap' },
                }}
              >
                <Button variant="contained" onClick={() => go('/sell')}>
                  List a business
                </Button>
                <Button color="inherit" onClick={() => go('/my-listings')} sx={{ color: 'text.secondary' }}>
                  My listings
                </Button>
                <Button color="inherit" component={RouterLink} to="/messages" sx={{ color: 'text.secondary' }}>
                  Messages
                  {unreadTotal > 0 && (
                    <Box
                      component="span"
                      sx={{
                        ml: 0.75,
                        minWidth: 20,
                        height: 20,
                        px: 0.5,
                        borderRadius: 999,
                        bgcolor: 'primary.main',
                        color: 'primary.contrastText',
                        display: 'inline-flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        fontSize: '0.7rem',
                        fontWeight: 700,
                      }}
                    >
                      {unreadTotal}
                    </Box>
                  )}
                </Button>
                <Button color="inherit" onClick={handleLogout} sx={{ color: 'text.secondary' }}>
                  Logout
                </Button>
              </Stack>

              {/* <sm: one control instead of three. */}
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
                slotProps={{ paper: { sx: { minWidth: 180, mt: 1 } } }}
              >
                <MenuItem onClick={() => go('/sell')}>List a business</MenuItem>
                <MenuItem onClick={() => go('/my-listings')}>My listings</MenuItem>
                <MenuItem onClick={() => go('/messages')}>
                  Messages{unreadTotal > 0 ? ` (${unreadTotal})` : ''}
                </MenuItem>
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
