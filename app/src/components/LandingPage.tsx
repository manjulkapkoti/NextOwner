// UI Pass 2 — the landing page, extracted verbatim (copy-wise) from App.tsx's
// inline `LandingRoute` JSX so the "first impression" pass can restyle it
// without the routing file growing further. Every word of the existing copy
// is unchanged (design_system_spec.md §7 — the succession voice is binding
// product copy); only staging/layout/type treatment changed.
//
// Rendered only for a logged-out visitor — `LandingRoute` in App.tsx redirects
// an authed visitor to /my-listings before this ever mounts. The CTA-
// destination branching below still checks `authStore.isAuthenticated`
// defensively, mirroring the one piece of auth-aware logic the original CTA
// never needed (it was always /browse, always public) so this keeps working
// correctly if that redirect logic ever moves.
import {
  Box,
  Card,
  Chip,
  Container,
  Divider,
  Stack,
  Typography,
} from '@mui/material'
import { observer } from 'mobx-react-lite'
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline'
import TravelExploreOutlinedIcon from '@mui/icons-material/TravelExploreOutlined'
import AssignmentTurnedInOutlinedIcon from '@mui/icons-material/AssignmentTurnedInOutlined'
import HandshakeOutlinedIcon from '@mui/icons-material/HandshakeOutlined'
import LockOutlinedIcon from '@mui/icons-material/LockOutlined'
import SellOutlined from '@mui/icons-material/SellOutlined'
import SearchOutlined from '@mui/icons-material/SearchOutlined'
import { blueTint, brandTint, elevation, surfaceRecessed } from '../theme'
import { authStore } from '../stores/authStore'
import { SpotlightCard } from './SpotlightCard'

// UI Pass 3 Part A — the two-sided "value cards" section, inserted between the
// hero and the 3-step gate band. No section header above them: the eyebrows
// (SELLERS / BUYERS) are the labels. Copy is locked in the spec — do not add a
// 4th bullet or a stat to either card.
const SELLER_POINTS = [
  'Every request for your financials needs your approval — nobody sees behind the gate without your yes',
  'One private data room per listing, not a public page anyone can screenshot and forward',
  "Buyers sign the platform NDA before they see a single number, not after you've already talked",
]

const BUYER_POINTS = [
  'No account needed to browse — sign up only when you want to ask a seller for access.',
  'One NDA covers every listing on the platform, signed once',
  'You see the shape of a deal before you ask — metrics, growth, price. The identity comes after.',
]

const trustPoints = ['Curated listings', 'NDA-gated data rooms', 'Verified buyers']

// The "how the gate works" 3-up band (audit item 6). Copy stays in the
// succession voice already established by the hero above it.
const gateSteps = [
  {
    number: '1',
    icon: TravelExploreOutlinedIcon,
    title: 'Browse anonymously',
    body: 'See the shape of any deal without an account.',
  },
  {
    number: '2',
    icon: AssignmentTurnedInOutlinedIcon,
    title: 'Sign one NDA',
    body: 'Covers every listing on the platform, once.',
  },
  {
    number: '3',
    icon: HandshakeOutlinedIcon,
    title: 'The seller decides',
    body: 'They choose who gets access to their numbers.',
  },
] as const

// A small composed mockup, not a screenshot -- built from the same tokens as
// the real ListingCard so it can never go visually stale. Deliberately not the
// real component: this is decorative preview content, captioned as such.
function MockMetric({ label, value }: { label: string; value: string }) {
  return (
    <Box sx={{ minWidth: 0 }}>
      <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
        {label}
      </Typography>
      <Typography sx={{ fontWeight: 600 }}>{value}</Typography>
    </Box>
  )
}

function MockListingCard({
  type,
  headline,
  price,
  metrics,
}: {
  type: string
  headline: string
  price: string
  metrics: [string, string][]
}) {
  return (
    <Card sx={{ p: 3, height: '100%', textAlign: 'left', boxShadow: elevation.lg }} aria-hidden>
      <Stack spacing={1.5} sx={{ height: '100%' }}>
        <Chip label={type} size="small" sx={{ alignSelf: 'flex-start' }} />
        <Typography variant="h6" component="p">
          {headline}
        </Typography>
        <Box
          sx={{
            ...surfaceRecessed,
            display: 'grid',
            gridTemplateColumns: 'repeat(3, minmax(0, 1fr))',
            gap: 1.5,
            p: 1.5,
          }}
        >
          {metrics.map(([label, value]) => (
            <MockMetric key={label} label={label} value={value} />
          ))}
        </Box>
        <Divider sx={{ mt: 'auto', mb: 1 }} />
        <Stack direction="row" alignItems="baseline" justifyContent="space-between">
          <Typography variant="caption" color="text.secondary">
            Asking price
          </Typography>
          <Typography variant="h6" component="p">
            {price}
          </Typography>
        </Stack>
      </Stack>
    </Card>
  )
}

function MockLockedCard() {
  return (
    <Card sx={{ p: 3, height: '100%', textAlign: 'left', boxShadow: elevation.lg }} aria-hidden>
      <Stack spacing={1.5} sx={{ height: '100%' }}>
        <Chip label="Ecommerce" size="small" sx={{ alignSelf: 'flex-start' }} />
        <Typography variant="h6" component="p">
          DTC specialty coffee subscription
        </Typography>
        <Box
          sx={{
            ...surfaceRecessed,
            p: 1.5,
            display: 'flex',
            alignItems: 'center',
            gap: 1.5,
          }}
        >
          <Box
            sx={{
              width: 24,
              height: 24,
              borderRadius: '50%',
              bgcolor: blueTint.wash,
              color: blueTint.onWash,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              flexShrink: 0,
            }}
          >
            <LockOutlinedIcon sx={{ fontSize: 14 }} />
          </Box>
          <Stack spacing={0.75} sx={{ flex: 1, minWidth: 0 }}>
            <Box sx={{ height: 8, borderRadius: 1, bgcolor: blueTint.placeholder, filter: 'blur(5px)', opacity: 0.8, width: '80%' }} />
            <Box sx={{ height: 8, borderRadius: 1, bgcolor: blueTint.placeholder, filter: 'blur(5px)', opacity: 0.8, width: '55%' }} />
          </Stack>
        </Box>
        <Divider sx={{ mt: 'auto', mb: 1 }} />
        <Stack direction="row" alignItems="baseline" justifyContent="space-between">
          <Typography variant="caption" color="text.secondary">
            Asking price
          </Typography>
          <Typography variant="h6" component="p">
            $340,000
          </Typography>
        </Stack>
      </Stack>
    </Card>
  )
}

export const LandingPage = observer(function LandingPage() {
  const sellDestination = authStore.isAuthenticated ? '/sell' : '/register'

  return (
    <Box
      sx={{
        // The dead full-viewport centering is gone (was `minHeight: calc(100vh
        // - 65px)` + `alignItems: center`) -- it produced a large empty scroll
        // area below the fold on anything taller than the hero. Real content
        // (the preview + the gate band) now fills that space instead.
        background: `radial-gradient(1100px 520px at 50% -8%, ${blueTint.wash}, ${brandTint} 45%, transparent 70%)`,
      }}
    >
      <Container maxWidth="md" sx={{ pt: { xs: 8, md: 14 }, pb: { xs: 6, md: 8 }, textAlign: 'center' }}>
        <Stack spacing={{ xs: 3, md: 3.5 }} alignItems="center">
          <Box
            sx={{
              px: 1.5,
              py: 0.5,
              borderRadius: 999,
              bgcolor: blueTint.wash,
            }}
          >
            <Typography variant="caption" sx={{ color: blueTint.onWash, fontWeight: 600, letterSpacing: '0.02em' }}>
              Succession, not transaction
            </Typography>
          </Box>

          <Typography
            variant="h2"
            component="h1"
            sx={{
              fontSize: 'clamp(2.5rem, 6vw, 3.75rem)',
              fontWeight: 800,
              letterSpacing: '-0.03em',
              lineHeight: 1.05,
              maxWidth: 780,
            }}
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

          {/* UI Pass 3 Part A, relocated (owner feedback): the hero's own
              "Browse listings" / "List your business" button pair is gone —
              these two spotlight cards now sit exactly where that button row
              used to be, carrying the same two CTAs but with real substance
              behind each, instead of duplicating them further down the page. */}
          <Box
            sx={{
              width: '100%',
              display: 'grid',
              gridTemplateColumns: { xs: '1fr', sm: 'repeat(2, minmax(0,1fr))' },
              gap: 3.5,
              textAlign: 'left',
              pt: 0.5,
            }}
          >
            <SpotlightCard
              icon={<SellOutlined sx={{ fontSize: 22, color: 'primary.main' }} />}
              eyebrow="SELLERS"
              heading="Choose who carries it forward"
              points={SELLER_POINTS}
              cta={{ label: 'List your business', to: sellDestination }}
            />
            <SpotlightCard
              icon={<SearchOutlined sx={{ fontSize: 22, color: 'primary.main' }} />}
              eyebrow="BUYERS"
              heading="Take over something real"
              points={BUYER_POINTS}
              cta={{ label: 'Browse listings', to: '/browse' }}
            />
          </Box>

          <Stack
            direction="row"
            spacing={1}
            flexWrap="wrap"
            alignItems="center"
            justifyContent="center"
            sx={{ pt: { xs: 2, md: 3 } }}
          >
            {trustPoints.map((point) => (
              <Chip
                key={point}
                icon={<CheckCircleOutlineIcon sx={{ fontSize: '1rem' }} />}
                label={point}
                size="small"
                sx={{
                  bgcolor: 'background.paper',
                  border: '1px solid',
                  borderColor: 'divider',
                  color: 'text.secondary',
                }}
              />
            ))}
          </Stack>
        </Stack>

        {/* The static product-preview mockup (audit item 5). Real composed
            markup, not a screenshot, so it can never go stale. */}
        <Box sx={{ maxWidth: 980, mx: 'auto', mt: { xs: 6, md: 8 }, position: 'relative' }}>
          <Box
            sx={{
              display: 'grid',
              gridTemplateColumns: { xs: '1fr', sm: 'repeat(3, minmax(0, 1fr))' },
              gap: 2.5,
              textAlign: 'left',
            }}
          >
            <MockListingCard
              type="SaaS"
              headline="Profitable B2B scheduling SaaS"
              price="$500,000"
              metrics={[
                ['MRR', '$18,000'],
                ['TTM profit', '$120,000'],
                ['Customers', '340'],
              ]}
            />
            <MockListingCard
              type="Content"
              headline="Niche newsletter, 4 years old"
              price="$210,000"
              metrics={[
                ['MRR', '$6,200'],
                ['TTM profit', '$48,000'],
                ['Customers', '12,400'],
              ]}
            />
            <MockLockedCard />
          </Box>

          {/* Bottom mask-fade, so the preview reads as a tease rather than a
              hard-edged screenshot. */}
          <Box
            aria-hidden
            sx={{
              position: 'absolute',
              left: 0,
              right: 0,
              bottom: 0,
              height: 64,
              pointerEvents: 'none',
              // Must match the page background exactly (`blueTint.page`, not
              // the old `neutral[25]`) or a visible hard edge appears where
              // the hero ends and the page ground begins.
              background: `linear-gradient(to bottom, transparent, ${blueTint.page})`,
            }}
          />

          <Typography
            variant="caption"
            color="text.secondary"
            sx={{ display: 'block', textAlign: 'center', mt: 2 }}
          >
            Example listings
          </Typography>
        </Box>
      </Container>

      {/* The "how the gate works" band (audit item 6), on the blue-tinted
          `brandTint`/`blueTint.band` background so it reads as a distinct
          band rather than a continuation of the hero. */}
      <Box sx={{ bgcolor: blueTint.band, borderTop: '1px solid', borderColor: blueTint.washBorder }}>
        <Container maxWidth="md" sx={{ py: { xs: 6, md: 8 } }}>
          <Box
            sx={{
              display: 'grid',
              gridTemplateColumns: { xs: '1fr', sm: 'repeat(3, minmax(0, 1fr))' },
              gap: { xs: 4, sm: 3 },
            }}
          >
            {gateSteps.map((step) => {
              const Icon = step.icon
              return (
                <Stack key={step.number} spacing={1.25} alignItems={{ xs: 'center', sm: 'flex-start' }} sx={{ textAlign: { xs: 'center', sm: 'left' } }}>
                  <Typography variant="overline" color="primary.main">
                    Step {step.number}
                  </Typography>
                  <Box
                    sx={{
                      width: 32,
                      height: 32,
                      borderRadius: '50%',
                      bgcolor: blueTint.wash,
                      color: blueTint.onWash,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                    }}
                  >
                    <Icon aria-hidden sx={{ fontSize: 18 }} />
                  </Box>
                  <Typography variant="subtitle1">{step.title}</Typography>
                  <Typography variant="body2" color="text.secondary">
                    {step.body}
                  </Typography>
                </Stack>
              )
            })}
          </Box>
        </Container>
      </Box>
    </Box>
  )
})
