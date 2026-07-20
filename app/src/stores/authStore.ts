// MobX auth store — holds the token + current user (constitution: MobX for state).
// The token lives in localStorage (see api.ts / security.md §Frontend session).
// Client state is convenience only — the server gate is the real boundary.
import { makeAutoObservable, runInAction } from 'mobx'
import { api, ApiError } from '../lib/api'

export interface CurrentUser {
  id: number
  email: string
  is_buyer: boolean
  is_seller: boolean
  is_admin: boolean
  display_name: string | null
  // M5 — the platform NDA is signed once, ever (FR-13), so whether to show the
  // click-wrap modal is a property of the *user*, not of any listing. Served on
  // `/api/auth/me`; null means never signed.
  nda_signed_at?: string | null
}

class AuthStore {
  token: string | null = localStorage.getItem('token')
  user: CurrentUser | null = null

  constructor() {
    makeAutoObservable(this)
  }

  get isAuthenticated() {
    return this.token !== null
  }

  setToken(token: string) {
    this.token = token
    localStorage.setItem('token', token)
  }

  /** Log in via the OAuth2 password form (form-encoded, not JSON). */
  async login(email: string, password: string): Promise<void> {
    const res = await fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: new URLSearchParams({ username: email, password }),
    })
    if (!res.ok) {
      const body = await res.json().catch(() => null)
      throw new ApiError(res.status, body?.code ?? null, body?.detail, body?.detail ?? 'Login failed')
    }
    const data = await res.json()
    this.setToken(data.access_token)
    await this.loadUser()
  }

  async loadUser(): Promise<void> {
    const user = await api('/auth/me')
    runInAction(() => {
      this.user = user
    })
  }

  logout() {
    this.token = null
    this.user = null
    localStorage.removeItem('token')
  }
}

export const authStore = new AuthStore()
