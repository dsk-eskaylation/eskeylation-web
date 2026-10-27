import { useState, type FormEvent } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { getSession, login } from '../api/auth'
import { FormError } from '../components/FormError'
import './Login.css'

/** Trang đăng nhập CMS — theo design language Figma "bàn giao DEV":
    nền tối + orb blur, card pill glass, input radius 52, lỗi đỏ #AF0A0A. */
export function Login() {
  const navigate = useNavigate()
  const [params] = useSearchParams()
  // Only same-site paths, so ?next= cannot send users to another origin.
  const nextPath = params.get('next')
  const next = nextPath?.startsWith('/') && !nextPath.startsWith('//') && !nextPath.startsWith('/\\') ? nextPath : null
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError(null)
    setBusy(true)
    try {
      await login(email, password)
      const user = await getSession()
      navigate(next ?? (user?.role === 'member' ? '/community' : '/cms'), { replace: true })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Đăng nhập thất bại')
    } finally {
      setBusy(false)
    }
  }

  return (
    <main className="login">
      <span className="login__orb" aria-hidden="true" />

      <form className="login__card page-enter" onSubmit={onSubmit}>
        <Link to="/" className="login__brand">
          ESKAYLATION
        </Link>
        <h1 className="login__sub">Đăng nhập Eskaylation</h1>

        <label className="login__field">
          <span className="login__label">Email</span>
          <input
            id="login-email"
            name="email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@eskaylation.com"
            autoComplete="username"
            spellCheck={false}
            aria-invalid={error ? true : undefined}
            aria-describedby={error ? 'login-error' : undefined}
            required
          />
        </label>

        <label className="login__field">
          <span className="login__label">Mật khẩu</span>
          <input
            name="password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="••••••••"
            autoComplete="current-password"
            aria-invalid={error ? true : undefined}
            aria-describedby={error ? 'login-error' : undefined}
            required
          />
        </label>

        {error && (
          <FormError id="login-error" message={error} fieldId="login-email" className="login__error" />
        )}

        <button type="submit" className="login__submit" disabled={busy}>
          {busy ? 'Đang đăng nhập…' : 'Đăng nhập'}
        </button>

        <Link to="/" className="login__back">
          ‹ Về trang chủ
        </Link>
      </form>
    </main>
  )
}
