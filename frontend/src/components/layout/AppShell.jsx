import { useState } from 'react'
import { Menu } from 'lucide-react'
import Sidebar from './Sidebar'

export default function AppShell({ title: _title, children, flush = false }) {
  const [mobileOpen, setMobileOpen] = useState(false)
  const [collapsed, setCollapsed] = useState(false)

  return (
    <div className="flex h-screen overflow-hidden bg-[var(--aal-bg)] text-[var(--aal-ink)]">
      <Sidebar
        open={mobileOpen}
        onClose={() => setMobileOpen(false)}
        collapsed={collapsed}
        onToggleCollapse={() => setCollapsed((value) => !value)}
      />

      <div className="relative flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
        <button
          type="button"
          onClick={() => setMobileOpen(true)}
          className="absolute left-4 top-4 z-30 rounded-lg border border-[var(--aal-line)] bg-[var(--aal-card)] p-2 text-[var(--aal-muted)] shadow-sm lg:hidden"
          aria-label="Open sidebar"
        >
          <Menu className="h-4 w-4" />
        </button>

        <main
          className={
            flush
              ? 'flex min-h-0 flex-1 flex-col overflow-hidden'
              : 'min-h-0 flex-1 overflow-y-auto px-4 py-6 pt-14 sm:px-6 lg:px-8 lg:pt-6'
          }
        >
          {children}
        </main>
      </div>
    </div>
  )
}
