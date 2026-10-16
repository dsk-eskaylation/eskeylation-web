import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { login } from '../api/auth'
import './Login.css'

/** Trang đăng nhập CMS — theo design language Figma "bàn giao DEV":
    nền tối + orb blur, card pill glass, input radius 52, lỗi đỏ #AF0A0A. */
export function Login() {
  const navigate = useNavigate()
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
      navigate('/cms', { replace: true })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Đăng nhập thất bại')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="login">
      <span className="login__orb" aria-hidden="true" />

      <form className="login__card page-enter" onSubmit={onSubmit}>
        <Link to="/" className="login__brand">
          ESKAYLATION
        </Link>
        <p className="login__sub">Khu vực quản trị nội dung</p>

        <label className="login__field">
          <span className="login__label">Email</span>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@eskaylation.com"
            autoComplete="username"
            required
          />
        </label>

        <label className="login__field">
          <span className="login__label">Mật khẩu</span>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="••••••••"
            autoComplete="current-password"
            required
          />
        </label>

        {error && (
          <p className="login__error">
            <span>*</span>
            {error}
          </p>
        )}

        <button type="submit" className="login__submit" disabled={busy}>
          {busy ? 'Đang đăng nhập…' : 'Đăng nhập'}
        </button>

        <Link to="/" className="login__back">
          ‹ Về trang chủ
        </Link>
      </form>
    </div>
  )
}
