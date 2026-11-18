import { NavLink, useLocation } from 'react-router-dom'
import { LayoutGrid, LayoutDashboard, Boxes, Waypoints, ScrollText } from 'lucide-react'

const ITEMS = [
  { to: '/workspaces', label: 'Home', icon: LayoutGrid, match: ['/workspaces'] },
  { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard, match: ['/dashboard'] },
  { to: '/pipelines', label: 'Pipelines', icon: Boxes, match: ['/pipelines'] },
  { to: '/pipelines/new', label: 'Editor', icon: Waypoints, match: ['/pipelines/new', '/pipelines/'] },
  { to: '/logs', label: 'Logs', icon: ScrollText, match: ['/logs'] },
]

export default function BottomDock() {
  const location = useLocation()

  const isActive = (item) => {
    const path = location.pathname
    if (item.to === '/pipelines') return path === '/pipelines'
    if (item.to === '/pipelines/new') {
      return path === '/pipelines/new' || /^\/pipelines\/[^/]+$/.test(path)
    }
    return path.startsWith(item.to)
  }

  return (
    <nav
      aria-label="Primary"
      className="fixed bottom-5 left-1/2 z-40 -translate-x-1/2 void-glass rounded-full px-2 py-2 shadow-[0_12px_40px_rgba(0,0,0,0.5)]"
    >
      <ul className="flex items-center gap-1">
        {ITEMS.map(item => {
          const Icon = item.icon
          const active = isActive(item)
          return (
            <li key={item.to}>
              <NavLink
                to={item.to}
                aria-label={item.label}
                aria-current={active ? 'page' : undefined}
                className={`void-focus flex items-center gap-2 rounded-full px-3.5 py-2 text-xs font-medium transition-all duration-200 ${
                  active
                    ? 'bg-accent/20 text-white shadow-glow-accent-sm'
                    : 'text-white/55 hover:text-white hover:bg-white/5'
                }`}
              >
                <Icon size={16} strokeWidth={2} />
                <span className="hidden sm:inline">{item.label}</span>
              </NavLink>
            </li>
          )
        })}
      </ul>
    </nav>
  )
}
