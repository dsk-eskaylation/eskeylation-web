import { useCallback, useEffect, useRef, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { getSession } from '../api/auth'
import { community, type NotificationItem } from '../api/community'
import './AuthButtons.css'
import './NotificationBell.css'

const POLL_MS = 30_000

const TEXT: Record<NotificationItem['kind'], string> = {
  post_reaction: 'đã bày tỏ cảm xúc về bài viết',
  post_comment: 'đã bình luận bài viết',
  comment_reaction: 'đã bày tỏ cảm xúc về bình luận của bạn trong',
}

function ago(iso: string): string {
  const m = Math.floor((Date.now() - new Date(iso).getTime()) / 60000)
  if (m < 1) return 'vừa xong'
  if (m < 60) return `${m} phút`
  const h = Math.floor(m / 60)
  if (h < 24) return `${h} giờ`
  return `${Math.floor(h / 24)} ngày`
}

/** Chuông thông báo cạnh nút tài khoản; chỉ hiện khi đã đăng nhập. */
export function NotificationBell() {
  const navigate = useNavigate()
  const location = useLocation()
  const [loggedIn, setLoggedIn] = useState(false)
  const [open, setOpen] = useState(false)
  const [data, setData] = useState<{ unread: number; items: NotificationItem[] }>({ unread: 0, items: [] })
  const rootRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    let live = true
    getSession().then((u) => live && setLoggedIn(u !== null))
    return () => { live = false }
  }, [location.pathname])

  const load = useCallback(() => {
    community.notifications().then(setData, () => {})
  }, [])

  useEffect(() => {
    if (!loggedIn) return
    load()
    const timer = window.setInterval(() => {
      if (document.visibilityState === 'visible') load()
    }, POLL_MS)
    return () => window.clearInterval(timer)
  }, [loggedIn, load])

  useEffect(() => {
    if (!open) return
    const onDown = (e: MouseEvent) => {
      if (!rootRef.current?.contains(e.target as Node)) setOpen(false)
    }
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false)
    }
    document.addEventListener('mousedown', onDown)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onDown)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  if (!loggedIn) return null

  function toggle() {
    const next = !open
    setOpen(next)
    if (next && data.unread > 0) {
      community.readNotifications().then(() => setData((d) => ({ ...d, unread: 0 })), () => {})
    }
  }

  function go(n: NotificationItem) {
    setOpen(false)
    if (n.content_type === 'music') navigate('/music')
    else if (n.content_slug) navigate(`/community?post=${encodeURIComponent(n.content_slug)}`)
  }

  return (
    <div className="auth-menu notif" ref={rootRef}>
      <button
        type="button"
        className={open ? 'auth-menu__trigger auth-menu__trigger--open' : 'auth-menu__trigger'}
        onClick={toggle}
        aria-haspopup="true"
        aria-expanded={open}
        aria-label={data.unread ? `Thông báo, ${data.unread} chưa đọc` : 'Thông báo'}
      >
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <path d="M6 16V11a6 6 0 1 1 12 0v5l1.5 2h-15zM10 20.5a2 2 0 0 0 4 0" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" />
        </svg>
        {data.unread > 0 && <span className="notif__badge" aria-hidden="true">{data.unread > 9 ? '9+' : data.unread}</span>}
      </button>
      {open && (
        <div className="auth-menu__panel notif__panel">
          <p className="notif__title">Thông báo</p>
          {data.items.length === 0 ? (
            <p className="notif__empty">Khi có người thích hoặc bình luận bài của bạn, thông báo sẽ hiện ở đây.</p>
          ) : (
            <ul className="notif__list">
              {data.items.map((n) => (
                <li key={n.id}>
                  <button type="button" className={n.read ? 'notif__item' : 'notif__item notif__item--new'} onClick={() => go(n)}>
                    <span className="notif__avatar" aria-hidden="true">{n.actor_name.slice(0, 1).toUpperCase()}</span>
                    <span>
                      <strong>{n.actor_name}</strong> {TEXT[n.kind]} {n.content_title && <em>“{n.content_title}”</em>}
                      <time dateTime={n.created_at}>{ago(n.created_at)}</time>
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  )
}
