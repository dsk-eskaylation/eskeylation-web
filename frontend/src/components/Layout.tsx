import { Outlet } from 'react-router-dom'
import { PillNav } from './PillNav'
import './Layout.css'

export function Layout() {
  return (
    <div className="layout">
      <header className="layout__nav">
        <PillNav />
      </header>
      <main className="layout__main">
        <Outlet />
      </main>
    </div>
  )
}
