import { useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { register } from '../api/auth'
import { FormError } from '../components/FormError'
import './Login.css'

/** Trang đăng ký — tái dùng toàn bộ style Login (cùng design language).
    Tài khoản tạo ra ở trạng thái chờ quản trị viên duyệt. */
export function Register() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [invalidField, setInvalidField] = useState<string | undefined>()
  const [done, setDone] = useState(false)
  const [busy, setBusy] = useState(false)

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError(null)
    setInvalidField(undefined)
    if (password.length < 8) {
      setError('Mật khẩu phải từ 8 ký tự trở lên')
      setInvalidField('register-password')
      return
    }
    if (password !== confirm) {
      setError('Mật khẩu nhập lại không khớp')
      setInvalidField('register-confirm')
      return
    }
    setBusy(true)
    try {
      await register(email, password)
      setDone(true)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Đăng ký thất bại')
    } finally {
      setBusy(false)
    }
  }

  if (done) {
    return (
      <main className="login">
        <span className="login__orb" aria-hidden="true" />
        <div className="login__card page-enter">
          <span className="login__brand">ESKAYLATION</span>
          <h1 className="login__sub">Đăng ký thành công!</h1>
          <p className="login__sub">
            Tài khoản của bạn đang chờ quản trị viên duyệt —
            bạn sẽ đăng nhập được sau khi được kích hoạt.
          </p>
          <Link to="/" className="login__submit login__submit--center">
            Về trang chủ
          </Link>
        </div>
      </main>
    )
  }

  return (
    <main className="login">
      <span className="login__orb" aria-hidden="true" />

      <form className="login__card page-enter" onSubmit={onSubmit}>
        <Link to="/" className="login__brand">
          ESKAYLATION
        </Link>
        <h1 className="login__sub">Tạo tài khoản — cần quản trị viên duyệt</h1>

        <label className="login__field">
          <span className="login__label">Email</span>
          <input
            id="register-email"
            name="email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@example.com"
            autoComplete="email"
            spellCheck={false}
            required
          />
        </label>

        <label className="login__field">
          <span className="login__label">Mật khẩu (tối thiểu 8 ký tự)</span>
          <input
            id="register-password"
            name="password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="••••••••"
            autoComplete="new-password"
            aria-invalid={invalidField === 'register-password' || undefined}
            aria-describedby={invalidField === 'register-password' ? 'register-error' : undefined}
            minLength={8}
            maxLength={128}
            required
          />
        </label>

        <label className="login__field">
          <span className="login__label">Nhập lại mật khẩu</span>
          <input
            id="register-confirm"
            name="confirm-password"
            type="password"
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            placeholder="••••••••"
            autoComplete="new-password"
            aria-invalid={invalidField === 'register-confirm' || undefined}
            aria-describedby={invalidField === 'register-confirm' ? 'register-error' : undefined}
            minLength={8}
            maxLength={128}
            required
          />
        </label>

        {error && (
          <FormError id="register-error" message={error} fieldId={invalidField} className="login__error" />
        )}

        <button type="submit" className="login__submit" disabled={busy}>
          {busy ? 'Đang đăng ký…' : 'Đăng ký'}
        </button>

        <Link to="/login" className="login__back">
          Đã có tài khoản? Đăng nhập
        </Link>
      </form>
    </main>
  )
}
