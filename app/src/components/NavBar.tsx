// Top nav — brand + (when authed) navigation and a Logout control (spec AS5).
// Auth-aware via authStore (MobX observer) so it re-renders on login/logout.
// This is chrome, not a security boundary — RequireAuth + the server gates
// the actual routes and data.
//
// Presentation only (design_system.md): the AppBar's white/translucent surface
// and hairline border come from the theme. Below `sm` the wordmark collapses
// to the brand mark so the authed action row never overflows a 375px phone.
import { AppBar, Box, Button, Container, Stack, Toolbar, Typography } from '@mui/material'
import { observer } from 'mobx-react-lite'
import { useNavigate } from 'react-router-dom'
import { authStore } from '../stores/authStore'

export const NavBar = observer(function NavBar() {
  const navigate = useNavigate()

  function handleLogout() {
    authStore.logout()
    navigate('/login')
  }

  return (
    <AppBar position="sticky">
      <Container maxWidth="lg">
        <Toolbar disableGutters sx={{ minHeight: 64, gap: 1 }}>
          <Stack direction="row" alignItems="center" spacing={1} sx={{ flexGrow: 1, minWidth: 0 }}>
            <Box
              aria-hidden
              sx={{
                width: 28,
                height: 28,
                flexShrink: 0,
                borderRadius: 1,
                bgcolor: 'primary.main',
                color: 'primary.contrastText',
                display: 'grid',
                placeItems: 'center',
                fontSize: 15,
                fontWeight: 700,
                lineHeight: 1,
              }}
            >
              N
            </Box>
            <Typography
              variant="h6"
              sx={{
                fontWeight: 700,
                letterSpacing: '-0.02em',
                display: { xs: 'none', sm: 'block' },
              }}
            >
              NextOwner
            </Typography>
          </Stack>

          {authStore.isAuthenticated && (
            <Stack
              direction="row"
              spacing={{ xs: 0.5, sm: 1 }}
              alignItems="center"
              sx={{ '& .MuiButton-root': { whiteSpace: 'nowrap' } }}
            >
              <Button
                variant="contained"
                size="small"
                onClick={() => navigate('/sell')}
                sx={{ fontSize: { xs: '0.8125rem', sm: '0.875rem' } }}
              >
                List a business
              </Button>
              <Button
                color="inherit"
                size="small"
                onClick={() => navigate('/my-listings')}
                sx={{ color: 'text.secondary', fontSize: { xs: '0.8125rem', sm: '0.875rem' } }}
              >
                My listings
              </Button>
              <Button
                color="inherit"
                size="small"
                onClick={handleLogout}
                sx={{ color: 'text.secondary', fontSize: { xs: '0.8125rem', sm: '0.875rem' } }}
              >
                Logout
              </Button>
            </Stack>
          )}
        </Toolbar>
      </Container>
    </AppBar>
  )
})
