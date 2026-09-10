import { NavLink } from 'react-router-dom'
import { Activity, HeartPulse, LayoutGrid } from 'lucide-react'
import { PROFILE_PAGES } from '../../utils/profileView'

const ICONS = {
  '/profile': LayoutGrid,
  '/profile/training': Activity,
  '/profile/zones': HeartPulse,
}

export default function ProfileSectionNav() {
  return (
    <nav
      aria-label="Profile sections"
      className="flex gap-1 overflow-x-auto p-1"
    >
      {PROFILE_PAGES.map((page) => {
        const Icon = ICONS[page.path] || LayoutGrid
        return (
          <NavLink
            key={page.path}
            to={page.path}
            end={page.end}
            className={({ isActive }) =>
              `flex shrink-0 items-center gap-2 rounded-xl px-3.5 py-2.5 text-sm font-medium transition ${
                isActive
                  ? 'bg-sage text-white shadow-sm'
                  : 'text-[var(--aal-muted)] hover:bg-[var(--aal-bg)] hover:text-[var(--aal-ink)]'
              }`
            }
          >
            <Icon className="h-4 w-4 shrink-0 opacity-90" aria-hidden />
            <span>{page.label}</span>
          </NavLink>
        )
      })}
    </nav>
  )
}
