import type { ReactNode } from 'react'
import { Navigate } from 'react-router-dom'
import { isLoggedIn } from '../api/auth'

/** Chặn route cần đăng nhập: chưa có token thì đá về /login. */
export function RequireAuth({ children }: { children: ReactNode }) {
  if (!isLoggedIn()) return <Navigate to="/login" replace />
  return children
}
