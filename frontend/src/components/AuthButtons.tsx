import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { clearToken, isLoggedIn } from '../api/auth'
import './AuthButtons.css'

/** Nút tài khoản góc phải mọi trang public: icon tròn kính mờ, bấm xổ dropdown.
    Chưa đăng nhập: Đăng nhập / Đăng ký. Đã đăng nhập: CMS / Đăng xuất.
    Gọn nên không đè PillNav; đóng khi bấm ra ngoài hoặc Escape. */
export function AuthButtons() {
  const navigate = useNavigate()
  const logged = isLoggedIn()
  const [open, setOpen] = useState(false)
  const rootRef = useRef<HTMLDivElement>(null)

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

  const logout = () => {
    clearToken()
    setOpen(false)
    navigate('/', { replace: true })
  }

  return (
    <div className="auth-menu" ref={rootRef}>
      <button
        type="button"
        className={open ? 'auth-menu__trigger auth-menu__trigger--open' : 'auth-menu__trigger'}
        onClick={() => setOpen((v) => !v)}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label="Tài khoản"
      >
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <circle cx="12" cy="8" r="4" fill="none" stroke="currentColor" strokeWidth="1.6" />
          <path
            d="M4.5 20c0-3.6 3.4-6 7.5-6s7.5 2.4 7.5 6"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.6"
            strokeLinecap="round"
          />
        </svg>
        {logged && <span className="auth-menu__dot" aria-hidden="true" />}
      </button>

      {open && (
        <div className="auth-menu__panel" role="menu">
          {logged ? (
            <>
              <Link
                to="/cms"
                role="menuitem"
                className="auth-menu__item auth-menu__item--primary"
                onClick={() => setOpen(false)}
              >
                Trang quản trị
              </Link>
              <button
                type="button"
                role="menuitem"
                className="auth-menu__item"
                onClick={logout}
              >
                Đăng xuất
              </button>
            </>
          ) : (
            <>
              <Link
                to="/login"
                role="menuitem"
                className="auth-menu__item auth-menu__item--primary"
                onClick={() => setOpen(false)}
              >
                Đăng nhập
              </Link>
              <Link
                to="/register"
                role="menuitem"
                className="auth-menu__item"
                onClick={() => setOpen(false)}
              >
                Đăng ký
              </Link>
            </>
          )}
        </div>
      )}
    </div>
  )
}
