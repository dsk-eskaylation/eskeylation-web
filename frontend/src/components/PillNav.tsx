import { NavLink } from 'react-router-dom'
import './PillNav.css'

const items = [
  { to: '/', label: 'Trang chủ', end: true },
  { to: '/music', label: 'Nghe nhạc' },
  { to: '/photos', label: 'Ảnh' },
  { to: '/video', label: 'Video' },
  { to: '/community', label: 'Cộng đồng' },
]

function linkClass({ isActive }: { isActive: boolean }) {
  return isActive ? 'pill-nav__link pill-nav__link--active' : 'pill-nav__link'
}

export function PillNav() {
  return (
    <nav className="pill-nav" aria-label="Điều hướng chính">
      {items.map((item) => (
        <NavLink key={item.to} to={item.to} end={item.end} className={linkClass}>
          {item.label}
        </NavLink>
      ))}
    </nav>
  )
}
