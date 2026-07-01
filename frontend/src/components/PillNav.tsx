import { NavLink } from 'react-router-dom'
import './PillNav.css'

const left = [
  { to: '/', label: 'Trang chủ', end: true },
  { to: '/music', label: 'Nghe nhạc' },
]
const right = [
  { to: '/photos', label: 'Ảnh' },
  { to: '/community', label: 'Cộng đồng' },
]

function linkClass({ isActive }: { isActive: boolean }) {
  return isActive ? 'pill-nav__link pill-nav__link--active' : 'pill-nav__link'
}

export function PillNav() {
  return (
    <nav className="pill-nav" aria-label="Điều hướng chính">
      <div className="pill-nav__group">
        {left.map((item) => (
          <NavLink key={item.to} to={item.to} end={item.end} className={linkClass}>
            {item.label}
          </NavLink>
        ))}
      </div>

      <NavLink to="/" className="pill-nav__brand">
        ESKAYLATION
      </NavLink>

      <div className="pill-nav__group">
        {right.map((item) => (
          <NavLink key={item.to} to={item.to} className={linkClass}>
            {item.label}
          </NavLink>
        ))}
      </div>
    </nav>
  )
}
