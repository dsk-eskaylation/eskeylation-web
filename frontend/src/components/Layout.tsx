import { Outlet, useLocation } from 'react-router-dom'
import { PillNav } from './PillNav'
import './Layout.css'

export function Layout() {
  const location = useLocation()
  return (
    <div className="layout">
      <header className="layout__nav">
        <PillNav />
      </header>
      {/* key theo pathname -> mỗi lần đổi trang chạy lại animation vào trang */}
      <main className="layout__main page-enter" key={location.pathname}>
        <Outlet />
      </main>
    </div>
  )
}
