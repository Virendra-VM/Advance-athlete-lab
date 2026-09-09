import { useEffect, useId, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { MoreVertical, Pencil, RefreshCw, ShieldCheck } from 'lucide-react'

/**
 * Overflow menu for season plan actions — keeps the header clean.
 */
export default function SeasonPlanMenu({
  disabled = false,
  replanTriggerCount = 0,
  onReplan,
  onRebuildFromScratch,
  onRebuildSeason,
}) {
  const menuId = useId()
  const rootRef = useRef(null)
  const [open, setOpen] = useState(false)

  useEffect(() => {
    if (!open) return undefined
    function onPointerDown(event) {
      if (!rootRef.current?.contains(event.target)) setOpen(false)
    }
    function onKey(event) {
      if (event.key === 'Escape') setOpen(false)
    }
    document.addEventListener('pointerdown', onPointerDown)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('pointerdown', onPointerDown)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  function closeAnd(run) {
    setOpen(false)
    run?.()
  }

  return (
    <div ref={rootRef} className="relative">
      <button
        type="button"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={menuId}
        disabled={disabled}
        onClick={() => setOpen((current) => !current)}
        className="inline-flex h-[38px] w-[38px] items-center justify-center rounded-xl border border-[var(--aal-line)] bg-[var(--aal-card)] text-[var(--aal-muted)] transition hover:border-indigo-300 hover:text-indigo-600 disabled:opacity-60 dark:hover:text-indigo-300"
        aria-label="Season plan options"
      >
        <MoreVertical className="h-4 w-4" />
      </button>

      {open ? (
        <div
          id={menuId}
          role="menu"
          className="absolute right-0 top-[calc(100%+6px)] z-50 w-56 overflow-hidden rounded-xl border border-[var(--aal-line)] bg-[var(--aal-card)] py-1 shadow-lg"
        >
          <Link
            to="/profile#profile-training"
            role="menuitem"
            onClick={() => setOpen(false)}
            className="flex w-full items-center gap-2.5 px-3 py-2.5 text-left text-sm text-[var(--aal-ink)] transition hover:bg-indigo-50/60 dark:hover:bg-indigo-950/30"
          >
            <Pencil className="h-4 w-4 shrink-0 text-indigo-500" />
            Edit A-race
          </Link>
          <button
            type="button"
            role="menuitem"
            onClick={() => closeAnd(onReplan)}
            className="flex w-full items-center gap-2.5 px-3 py-2.5 text-left text-sm text-[var(--aal-ink)] transition hover:bg-indigo-50/60 dark:hover:bg-indigo-950/30"
          >
            <ShieldCheck className="h-4 w-4 shrink-0 text-indigo-500" />
            <span className="min-w-0">
              Replan remaining weeks
              {replanTriggerCount > 0 ? (
                <span className="ml-1 text-xs font-semibold text-amber-600 dark:text-amber-300">
                  ({replanTriggerCount})
                </span>
              ) : null}
            </span>
          </button>
          <div className="my-1 border-t border-[var(--aal-line)]" role="separator" />
          <button
            type="button"
            role="menuitem"
            onClick={() => closeAnd(onRebuildFromScratch)}
            className="flex w-full items-center gap-2.5 px-3 py-2.5 text-left text-sm text-[var(--aal-ink)] transition hover:bg-amber-50/60 dark:hover:bg-amber-950/20"
          >
            <RefreshCw className="h-4 w-4 shrink-0 text-amber-600 dark:text-amber-400" />
            Rebuild from scratch
          </button>
          <button
            type="button"
            role="menuitem"
            onClick={() => closeAnd(onRebuildSeason)}
            className="flex w-full items-center gap-2.5 px-3 py-2.5 text-left text-sm text-[var(--aal-ink)] transition hover:bg-amber-50/60 dark:hover:bg-amber-950/20"
          >
            <RefreshCw className="h-4 w-4 shrink-0 text-amber-600 dark:text-amber-400" />
            Rebuild season
          </button>
        </div>
      ) : null}
    </div>
  )
}
