import { Link } from 'react-router-dom'
import { Activity } from 'lucide-react'
import ThemeToggle from './ThemeToggle'
import UserMenu from './UserMenu'

export default function Navigation({ subtitle, showProfileLink = true }) {
  return (
    <header className="sticky top-0 z-50 w-full border-b border-slate-200/80 bg-white/90 backdrop-blur-md dark:border-white/10 dark:bg-gray-900/90">
      <div className="flex w-full items-center justify-between px-4 py-4 sm:px-6 lg:px-10 xl:px-12">
        <Link to="/dashboard" className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-sage/10 text-sage dark:bg-sage/20">
            <Activity className="h-5 w-5" />
          </div>
          <div>
            <p className="text-xs font-semibold uppercase tracking-widest text-sage">
              Advance Athlete Lab
            </p>
            {subtitle && (
              <h1 className="text-lg font-bold text-slate-900 dark:text-white">{subtitle}</h1>
            )}
          </div>
        </Link>

        <div className="flex items-center gap-3">
          {showProfileLink && <UserMenu />}
          <ThemeToggle />
        </div>
      </div>
    </header>
  )
}
