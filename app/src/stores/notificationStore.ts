// MobX notification store — the inbox reads + the nav badge count (M8, spec 008).
//
// Mirrors `chatStore`'s shape: the store owns loading/error state so a
// component never has to reimplement "is this a real failure or an empty
// list", and the unread count lives here rather than in `NavBar` so the badge
// and the inbox cannot disagree about it after a mark-read.
import { makeAutoObservable, runInAction } from 'mobx'
import { api } from '../lib/api'

export interface Notification {
  id: number
  type: string
  title: string
  listing_id: number | null
  conversation_id: number | null
  offer_id: number | null
  read_at: string | null
  created_at: string
}

export type InboxStatus = 'idle' | 'loading' | 'ready' | 'error'

// Where a notification takes you when clicked. Kept as one map rather than a
// chain of `if (n.listing_id)` in the component, for the same reason
// `chatStore`'s CLOSE_CODE_MESSAGES is one map: a routing rule with one home
// cannot drift between the two places that need it.
export function linkFor(notification: Notification): string {
  if (notification.conversation_id !== null) return `/messages/${notification.conversation_id}`
  if (notification.offer_id !== null) return '/my/offers'
  if (notification.listing_id !== null) return `/listings/${notification.listing_id}`
  return '/notifications'
}

class NotificationStore {
  notifications: Notification[] = []
  unreadCount = 0
  status: InboxStatus = 'idle'

  constructor() {
    makeAutoObservable(this)
  }

  async load(): Promise<void> {
    runInAction(() => {
      this.status = 'loading'
    })
    try {
      const rows = (await api('/notifications')) as Notification[]
      runInAction(() => {
        this.notifications = rows
        this.status = 'ready'
      })
    } catch {
      runInAction(() => {
        this.status = 'error'
      })
    }
  }

  async loadUnreadCount(): Promise<void> {
    try {
      const body = (await api('/notifications/unread-count')) as { unread_count: number }
      runInAction(() => {
        this.unreadCount = body.unread_count
      })
    } catch {
      // The badge is decoration; a failure here must never break the nav bar.
      runInAction(() => {
        this.unreadCount = 0
      })
    }
  }

  async markRead(id: number): Promise<void> {
    const updated = (await api(`/notifications/${id}/read`, { method: 'POST' })) as Notification
    runInAction(() => {
      this.notifications = this.notifications.map((n) => (n.id === id ? updated : n))
      this.unreadCount = Math.max(0, this.unreadCount - 1)
    })
  }

  reset(): void {
    this.notifications = []
    this.unreadCount = 0
    this.status = 'idle'
  }
}

export const notificationStore = new NotificationStore()
