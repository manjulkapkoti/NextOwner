// A single label/value KPI pair, using the `metricLabel`/`metricValue` sx
// tokens (theme.ts, UI Pass 1) so every metric in the app reads identically.
//
// This will later replace the near-duplicate `Metric`/`Figure` helper
// functions inside ListingCard.tsx and ListingDetail.tsx -- not touched in
// this pass, just built so Pass 2 can import it.
import { Box, Typography } from '@mui/material'
import { metricLabel, metricValue } from '../theme'

export interface MetricProps {
  label: string
  value: string
}

export function Metric({ label, value }: MetricProps) {
  return (
    <Box>
      <Typography component="div" sx={metricLabel}>
        {label}
      </Typography>
      <Typography component="div" sx={metricValue}>
        {value}
      </Typography>
    </Box>
  )
}
