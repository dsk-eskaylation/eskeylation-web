/** Auth client: login lấy JWT từ backend, giữ token trong localStorage. */

const TOKEN_KEY = 'esk_token'

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token)
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY)
}

export function isLoggedIn(): boolean {
  return getToken() !== null
}

/** POST /auth/login (OAuth2 form: username = email). Trả access_token. */
export async function login(email: string, password: string): Promise<void> {
  const body = new URLSearchParams({ username: email, password })
  const res = await fetch('/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body,
  })
  if (!res.ok) {
    const data = await res.json().catch(() => null)
    throw new Error(data?.detail ?? `Đăng nhập lỗi ${res.status}`)
  }
  const data = (await res.json()) as { access_token: string }
  setToken(data.access_token)
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

export function authHeaders(): Record<string, string> {
  const token = getToken()
  return token ? { Authorization: `Bearer ${token}` } : {}
}
