// The app shell — routes the components M1/M2 built into a usable app
// (spec pre-003). Replaces the M0 health page.
import { Container } from '@mui/material'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { ListingWizard } from './components/ListingWizard'
import { LoginForm } from './components/LoginForm'
import { MyListings } from './components/MyListings'
import { RequireAuth } from './components/RequireAuth'

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

export function AppShell() {
  return (
    <Routes>
      <Route path="/login" element={<LoginRoute />} />
      <Route path="/" element={<RequireAuth><Navigate to="/my-listings" replace /></RequireAuth>} />
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
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <AppShell />
    </BrowserRouter>
  )
}
