import { Link, Outlet, useLocation } from 'react-router-dom'
import { Suspense, useLayoutEffect } from 'react'
import { createPortal } from 'react-dom'
import { PillNav } from './PillNav'
import { AuthButtons } from './AuthButtons'
import { PlayerBar } from './PlayerBar'
import { usePlayer } from '../player/PlayerContext'
import bgTexture from '../assets/figma/bg-texture.png'
import './Layout.css'

export function Layout() {
  const location = useLocation()
  const hasPlayer = usePlayer().current !== null
  useLayoutEffect(() => {
    window.scrollTo({ top: 0, left: 0, behavior: 'instant' })
  }, [location.pathname])
  return (
    <div className={hasPlayer ? 'layout layout--with-player' : 'layout'}>
      <div className="layout__bg" aria-hidden="true" style={{ backgroundImage: `url(${bgTexture})` }} />
      <a className="skip-link" href="#main-content">Bỏ qua điều hướng</a>
      {createPortal(
        <header className="layout__nav">
          {/* Wordmark neo góc trái, đối xứng với nút tài khoản góc phải */}
          <Link to="/" className="layout__brand">
            ESKAYLATION
          </Link>
          <PillNav />
          <div className="layout__auth">
            <AuthButtons />
          </div>
        </header>,
        document.body,
      )}
      {/* key theo pathname -> mỗi lần đổi trang chạy lại animation vào trang */}
      <main id="main-content" tabIndex={-1} className="layout__main page-enter" key={location.pathname}>
        <Suspense
          fallback={
            <div className="route-loading" role="status">
              Đang tải…
            </div>
          }
        >
          <Outlet />
        </Suspense>
      </main>
      <PlayerBar />
    </div>
  )
}
