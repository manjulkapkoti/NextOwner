// Vitest setup — makes jest-dom matchers (toBeInTheDocument, …) available and
// clears the DOM between tests. Wired via `test.setupFiles` in vite.config.ts.
import '@testing-library/jest-dom'
import { afterEach } from 'vitest'
import { cleanup } from '@testing-library/react'

afterEach(() => cleanup())
