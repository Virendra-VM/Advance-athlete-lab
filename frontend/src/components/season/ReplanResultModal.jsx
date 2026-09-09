import { useEffect, useId, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { CheckCircle2, ChevronDown, X } from 'lucide-react'
import { formatSeasonDate, phaseAccent, phaseLabel } from '../../utils/seasonGuides'

const CHANGE_LABELS = {
  shifted: 'moved',
  added: 'added',
  removed: 'removed',
}

function DiffRow({ row }) {
  const accent = phaseAccent(row.phase_type)
  return (
    <li className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5 py-1.5">
      <span
        className={`rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide ${accent.chip}`}
      >
        {phaseLabel(row.phase_type)}
      </span>
      <span className="text-[11px] font-medium uppercase tracking-wide text-[var(--aal-muted)]">
        {CHANGE_LABELS[row.change] || row.change}
      </span>
      <span className="text-xs tabular-nums text-[var(--aal-muted)]">
        {row.before_start ? (
          <span className="line-through opacity-70">
            {formatSeasonDate(row.before_start, { withYear: false })} –{' '}
            {formatSeasonDate(row.before_end, { withYear: false })}
          </span>
        ) : null}
        {row.before_start && row.after_start ? <span className="mx-1.5">→</span> : null}
        {row.after_start ? (
          <span className="font-medium text-[var(--aal-ink)]">
            {formatSeasonDate(row.after_start, { withYear: false })} –{' '}
            {formatSeasonDate(row.after_end, { withYear: false })}
          </span>
        ) : null}
      </span>
    </li>
  )
}

export default function ReplanResultModal({ open, result, onClose }) {
  const titleId = useId()
  const [showDetail, setShowDetail] = useState(false)

  useEffect(() => {
    if (!open) {
      setShowDetail(false)
      return undefined
    }
    function onKey(event) {
      if (event.key === 'Escape') onClose?.()
    }
    document.addEventListener('keydown', onKey)
    const previous = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', onKey)
      document.body.style.overflow = previous
    }
  }, [open, onClose])

  const summary = result?.summary || []
  const diff = result?.diff || []

  return (
    <AnimatePresence>
      {open && result ? (
        <motion.div
          className="fixed inset-0 z-[92] flex items-end justify-center bg-black/50 p-4 sm:items-center"
          onClick={onClose}
          role="presentation"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
        >
          <motion.div
            role="dialog"
            aria-modal="true"
            aria-labelledby={titleId}
            className="flex max-h-[90vh] w-full max-w-lg flex-col overflow-hidden rounded-2xl border border-indigo-500/30 bg-[var(--aal-card)] shadow-xl"
            onClick={(event) => event.stopPropagation()}
            initial={{ opacity: 0, y: 24, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 16, scale: 0.98 }}
          >
            <div className="flex items-start justify-between gap-3 border-b border-[var(--aal-line)] px-5 py-4">
              <div className="flex items-start gap-3">
                <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-indigo-600 dark:text-indigo-300" />
                <div>
                  <h2 id={titleId} className="text-lg font-bold text-[var(--aal-ink)]">
                    {result.replanned ? 'Season updated' : 'No changes needed'}
                  </h2>
                  <p className="mt-0.5 text-sm text-[var(--aal-muted)]">{result.message}</p>
                </div>
              </div>
              <button
                type="button"
                onClick={onClose}
                aria-label="Close"
                className="shrink-0 rounded-lg border border-[var(--aal-line)] p-1.5 text-[var(--aal-muted)] transition hover:text-[var(--aal-ink)]"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4">
              {summary.length ? (
                <ul className="space-y-1.5">
                  {summary.map((line) => (
                    <li
                      key={line}
                      className="flex gap-2 text-sm leading-snug text-[var(--aal-ink)]"
                    >
                      <span
                        aria-hidden="true"
                        className="mt-[0.45rem] h-1.5 w-1.5 shrink-0 rounded-full bg-indigo-500"
                      />
                      <span>{line}</span>
                    </li>
                  ))}
                </ul>
              ) : null}

              {diff.length ? (
                <>
                  <button
                    type="button"
                    onClick={() => setShowDetail((current) => !current)}
                    className="mt-4 inline-flex items-center gap-1.5 text-xs font-medium text-indigo-600 transition hover:text-indigo-500 dark:text-indigo-300"
                  >
                    <ChevronDown
                      className={`h-3.5 w-3.5 transition-transform ${showDetail ? 'rotate-180' : ''}`}
                    />
                    {showDetail ? 'Hide' : 'Show'} every block that moved ({diff.length})
                  </button>
                  <AnimatePresence initial={false}>
                    {showDetail ? (
                      <motion.ul
                        initial={{ height: 0, opacity: 0 }}
                        animate={{ height: 'auto', opacity: 1 }}
                        exit={{ height: 0, opacity: 0 }}
                        transition={{ duration: 0.2 }}
                        className="mt-1 divide-y divide-[var(--aal-line)] overflow-hidden"
                      >
                        {diff.map((row) => (
                          <DiffRow
                            key={`${row.phase_type}-${row.occurrence}-${row.change}`}
                            row={row}
                          />
                        ))}
                      </motion.ul>
                    ) : null}
                  </AnimatePresence>
                </>
              ) : null}
            </div>

            <div className="border-t border-[var(--aal-line)] px-5 py-3">
              <button
                type="button"
                onClick={onClose}
                className="w-full rounded-xl bg-indigo-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-indigo-500"
              >
                Done
              </button>
            </div>
          </motion.div>
        </motion.div>
      ) : null}
    </AnimatePresence>
  )
}
