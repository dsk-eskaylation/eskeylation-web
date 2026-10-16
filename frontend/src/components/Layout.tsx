import { Link, Outlet, useLocation } from 'react-router-dom'
import { Suspense, useLayoutEffect } from 'react'
import { PillNav } from './PillNav'
import { AuthButtons } from './AuthButtons'
import { PlayerBar } from './PlayerBar'
import { usePlayer } from '../player/PlayerContext'
import './Layout.css'

export function Layout() {
  const location = useLocation()
  const hasPlayer = usePlayer().current !== null
  useLayoutEffect(() => {
    window.scrollTo({ top: 0, left: 0, behavior: 'instant' })
  }, [location.pathname])
  return (
    <div className={hasPlayer ? 'layout layout--with-player' : 'layout'}>
      <header className="layout__nav">
        {/* Wordmark neo góc trái, đối xứng với nút tài khoản góc phải */}
        <Link to="/" className="layout__brand">
          ESKAYLATION
        </Link>
        <PillNav />
        <div className="layout__auth">
          <AuthButtons />
        </div>
      </header>
      {/* key theo pathname -> mỗi lần đổi trang chạy lại animation vào trang */}
      <main className="layout__main page-enter" key={location.pathname}>
        <Suspense fallback={<div className="route-loading" role="status">Đang tải…</div>}><Outlet /></Suspense>
      </main>
      <PlayerBar />
    </div>
  )
}
