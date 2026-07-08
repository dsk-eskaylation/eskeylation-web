/** Auth client theo phiên COOKIE httpOnly:
    - JS không giữ/đọc token (chống XSS trộm token) — trình duyệt tự gửi cookie.
    - Mọi request auth dùng credentials: 'include'.
    - Request mutating gửi kèm X-CSRF-Token đọc từ cookie esk_csrf (double-submit).
    - Trạng thái đăng nhập xác định qua GET /auth/me (cache theo module). */

export interface SessionUser {
  id: number
  email: string
  role: 'admin' | 'editor' | 'author'
  is_active: boolean
}

/** Đọc CSRF token từ cookie esk_csrf (cookie này KHÔNG httpOnly). */
export function csrfToken(): string | null {
  const match = document.cookie.match(/(?:^|;\s*)esk_csrf=([^;]+)/)
  return match ? decodeURIComponent(match[1]) : null
}

/** Header cho request mutating (POST/PATCH/DELETE) qua phiên cookie. */
export function csrfHeaders(): Record<string, string> {
  const token = csrfToken()
  return token ? { 'X-CSRF-Token': token } : {}
}

// ---- Session cache: /auth/me chỉ gọi 1 lần, mọi nơi dùng chung ----
let sessionCache: Promise<SessionUser | null> | null = null

export function getSession(): Promise<SessionUser | null> {
  sessionCache ??= fetch('/auth/me', { credentials: 'include' })
    .then((res) => (res.ok ? (res.json() as Promise<SessionUser>) : null))
    .catch(() => null)
  return sessionCache
}

export function clearSessionCache(): void {
  sessionCache = null
}

/** POST /auth/login (OAuth2 form: username = email). Server set cookie phiên. */
export async function login(email: string, password: string): Promise<void> {
  const body = new URLSearchParams({ username: email, password })
  const res = await fetch('/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body,
    credentials: 'include',
  })
  if (!res.ok) {
    const data = await res.json().catch(() => null)
    throw new Error(data?.detail ?? `Đăng nhập lỗi ${res.status}`)
  }
  clearSessionCache()
}

/** POST /auth/logout — server xoá cookie phiên. */
export async function logout(): Promise<void> {
  await fetch('/auth/logout', {
    method: 'POST',
    credentials: 'include',
    headers: csrfHeaders(),
  }).catch(() => null)
  clearSessionCache()
}

/** POST /auth/register — tài khoản tạo ra ở trạng thái chờ admin duyệt. */
export async function register(email: string, password: string): Promise<void> {
  const res = await fetch('/auth/register', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  })
  if (!res.ok) {
    const data = await res.json().catch(() => null)
    const detail = typeof data?.detail === 'string' ? data.detail : null
    throw new Error(detail ?? `Đăng ký lỗi ${res.status}`)
  }
}
