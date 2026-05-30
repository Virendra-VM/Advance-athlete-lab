import { Link } from 'react-router-dom'
import { ChevronDown, LogOut, Settings, User } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import UserAvatar from './UserAvatar'

export default function UserMenu() {
  const { profile, logout } = useAuth()
  if (!profile) return null

  return (
    <div className="group relative">
      <Link
        to="/profile"
        className="flex items-center gap-2 rounded-full border border-slate-200 bg-slate-50 px-3 py-1.5 dark:border-white/10 dark:bg-gray-800"
      >
        <UserAvatar letter={profile.avatar_letter} name={profile.name} size="sm" />
        <span className="hidden text-sm font-medium text-slate-700 dark:text-slate-200 sm:inline">
          {profile.name}
        </span>
        <ChevronDown className="h-4 w-4 text-slate-400 transition-transform group-hover:rotate-180" />
      </Link>

      <div className="invisible absolute right-0 top-full z-50 w-44 pt-2 opacity-0 transition-all group-hover:visible group-hover:opacity-100">
        <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-lg dark:border-white/10 dark:bg-gray-900">
          <Link
            to="/profile"
            className="flex items-center gap-2 px-4 py-2.5 text-sm text-slate-700 hover:bg-slate-50 dark:text-slate-200 dark:hover:bg-gray-800"
          >
            <User className="h-4 w-4" /> Profile
          </Link>
          <Link
            to="/settings"
            className="flex items-center gap-2 px-4 py-2.5 text-sm text-slate-700 hover:bg-slate-50 dark:text-slate-200 dark:hover:bg-gray-800"
          >
            <Settings className="h-4 w-4" /> Settings
          </Link>
          <button
            type="button"
            onClick={logout}
            className="flex w-full items-center gap-2 px-4 py-2.5 text-left text-sm text-slate-700 hover:bg-slate-50 dark:text-slate-200 dark:hover:bg-gray-800"
          >
            <LogOut className="h-4 w-4" /> Log out
          </button>
        </div>
      </div>
    </div>
  )
}
