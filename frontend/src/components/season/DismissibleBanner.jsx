import { useEffect, useMemo, useState } from 'react'
import { ChevronDown, X } from 'lucide-react'

function storageKey(id) {
  return `aal-dismiss-${id}`
}

/**
 * Compact, dismissible banner — collapsed by default when children are long.
 */
export default function DismissibleBanner({
  id,
  tone = 'amber',
  icon: Icon,
  title,
  children,
  action = null,
  defaultExpanded = false,
}) {
  const dismissId = useMemo(() => (id ? storageKey(id) : null), [id])
  const [dismissed, setDismissed] = useState(false)
  const [expanded, setExpanded] = useState(defaultExpanded)

  useEffect(() => {
    if (!dismissId) return
    setDismissed(sessionStorage.getItem(dismissId) === '1')
  }, [dismissId])

  if (dismissed) return null

  const toneClasses =
    tone === 'amber'
      ? 'border-amber-500/35 bg-amber-500/10 text-amber-950 dark:text-amber-50'
      : 'border-indigo-500/30 bg-indigo-500/8 text-[var(--aal-ink)]'

  function dismiss() {
    if (dismissId) sessionStorage.setItem(dismissId, '1')
    setDismissed(true)
  }

  return (
    <div className={`rounded-xl border px-3 py-2.5 sm:px-4 ${toneClasses}`}>
      <div className="flex items-start gap-2">
        {Icon ? <Icon className="mt-0.5 h-4 w-4 shrink-0 opacity-90" /> : null}
        <div className="min-w-0 flex-1">
          <div className="flex items-start justify-between gap-2">
            <button
              type="button"
              onClick={() => setExpanded((current) => !current)}
              className="group flex min-w-0 flex-1 items-center gap-1.5 text-left"
            >
              <p className="text-sm font-semibold leading-snug">{title}</p>
              <ChevronDown
                className={`h-3.5 w-3.5 shrink-0 opacity-70 transition group-hover:opacity-100 ${
                  expanded ? 'rotate-180' : ''
                }`}
              />
            </button>
            <div className="flex shrink-0 items-center gap-1">
              {action}
              <button
                type="button"
                onClick={dismiss}
                className="rounded-lg p-1 opacity-70 transition hover:bg-black/5 hover:opacity-100 dark:hover:bg-white/10"
                aria-label="Dismiss"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            </div>
          </div>
          {expanded ? <div className="mt-2 text-sm leading-snug opacity-90">{children}</div> : null}
        </div>
      </div>
    </div>
  )
}
