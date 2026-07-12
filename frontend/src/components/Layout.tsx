import { Link, Outlet, useLocation } from 'react-router-dom'
import { PillNav } from './PillNav'
import { AuthButtons } from './AuthButtons'
import { PlayerBar } from './PlayerBar'
import { usePlayer } from '../player/PlayerContext'
import './Layout.css'

export function Layout() {
  const location = useLocation()
  const hasPlayer = usePlayer().current !== null
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
        <Outlet />
      </main>
      <PlayerBar />
    </div>
  )
}
