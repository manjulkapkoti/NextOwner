// Top nav — brand + (when authed) navigation and a Logout control (spec AS5).
// Auth-aware via authStore (MobX observer) so it re-renders on login/logout.
// This is chrome, not a security boundary — RequireAuth + the server gates
// the actual routes and data.
import { AppBar, Box, Button, Toolbar, Typography } from '@mui/material'
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
    <AppBar position="static">
      <Toolbar>
        <Typography variant="h6" sx={{ flexGrow: 1 }}>
          NextOwner
        </Typography>
        {authStore.isAuthenticated && (
          <Box sx={{ display: 'flex', gap: 1 }}>
            <Button color="inherit" onClick={() => navigate('/sell')}>
              List a business
            </Button>
            <Button color="inherit" onClick={() => navigate('/my-listings')}>
              My listings
            </Button>
            <Button color="inherit" onClick={handleLogout}>
              Logout
            </Button>
          </Box>
        )}
      </Toolbar>
    </AppBar>
  )
})
