import { NavLink, useLocation } from 'react-router-dom'
import { Shield, Cpu, Search, BookOpen, Play } from 'lucide-react'
import './Navbar.css'

const navLinks = [
  { path: '/', label: 'Overview', icon: Shield },
  { path: '/simulator', label: 'Simulator', icon: Play },
  { path: '/audit', label: 'Audit', icon: Search },
  { path: '/explorer', label: 'Merkle Explorer', icon: Cpu },
  { path: '/glossary', label: 'Glossary', icon: BookOpen },
]

export default function Navbar() {
  const location = useLocation()

  return (
    <nav className="navbar" role="navigation" aria-label="Main navigation">
      <div className="navbar__inner">
        {/* Logo / Brand */}
        <NavLink to="/" className="navbar__brand" aria-label="DHMC Dashboard Home">
          <div className="navbar__logo">
            <Shield size={22} strokeWidth={2.5} />
          </div>
          <div className="navbar__brand-text">
            <span className="navbar__brand-name">DHMC</span>
            <span className="navbar__brand-subtitle">Dashboard</span>
          </div>
        </NavLink>

        {/* Navigation Links */}
        <div className="navbar__links">
          {navLinks.map(({ path, label, icon: Icon }) => (
            <NavLink
              key={path}
              to={path}
              className={({ isActive }) =>
                `navbar__link ${isActive ? 'navbar__link--active' : ''}`
              }
              end={path === '/'}
            >
              <Icon size={16} />
              <span>{label}</span>
            </NavLink>
          ))}
        </div>

        {/* Status indicator */}
        <div className="navbar__status">
          <span className="navbar__status-dot"></span>
          <span className="navbar__status-text">System Ready</span>
        </div>
      </div>
    </nav>
  )
}
