import { useEffect, useState, type ReactNode } from 'react'
import { Navigate } from 'react-router-dom'
import { getSession } from '../api/auth'

/** Chặn route cần đăng nhập. Phiên nằm trong cookie httpOnly nên JS không
    tự đọc được — xác định qua GET /auth/me (có cache module). */
export function RequireAuth({ children }: { children: ReactNode }) {
  const [state, setState] = useState<'checking' | 'ok' | 'no' | 'member'>('checking')

  useEffect(() => {
    let alive = true
    getSession().then((user) => {
      if (alive) setState(user ? user.role === 'member' ? 'member' : 'ok' : 'no')
    })
    return () => {
      alive = false
    }
  }, [])

  if (state === 'checking') return null
  if (state === 'no') return <Navigate to="/login" replace />
  if (state === 'member') return <Navigate to="/community" replace />
  return children
}
