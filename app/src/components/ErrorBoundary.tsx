// Top-level error boundary — a render-time crash shows a fallback, never a white
// screen (spec H4, error_handling.md §3). Class component because React error
// boundaries require the lifecycle methods.
import { Component, type ErrorInfo, type ReactNode } from 'react'
import { Alert, Box } from '@mui/material'

interface Props {
  children: ReactNode
}
interface State {
  hasError: boolean
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false }

  static getDerivedStateFromError(): State {
    return { hasError: true }
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    // Local stand-in for real error monitoring (error_handling.md §6).
    console.error('ErrorBoundary caught:', error, info.componentStack)
  }

  render(): ReactNode {
    if (this.state.hasError) {
      return (
        <Box sx={{ p: 3 }}>
          <Alert severity="error">
            Something went wrong. Please reload the page and try again.
          </Alert>
        </Box>
      )
    }
    return this.props.children
  }
}
