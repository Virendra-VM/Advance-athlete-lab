import { useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { CheckCircle2, ChevronDown, X } from 'lucide-react'
import { formatSeasonDate, phaseAccent, phaseLabel } from '../../utils/seasonGuides'

/**
 * What a replan actually changed.
 *
 * The API returns two views. `summary` rolls the change up into phase totals and
 * boundary dates, which is the useful answer. `diff` is the exact block-by-block
 * record — accurate but noisy, because relaying out a season moves every
 * recovery week, so it sits behind a disclosure for anyone who wants to audit it.
 */

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

export default function ReplanResultCard({ result, onDismiss }) {
  const [showDetail, setShowDetail] = useState(false)
  if (!result) return null

  const summary = result.summary || []
  const diff = result.diff || []

  return (
    <motion.div
      initial={{ opacity: 0, y: -6 }}
      animate={{ opacity: 1, y: 0 }}
      className="rounded-2xl border border-indigo-500/30 bg-indigo-500/[0.07] px-4 py-4 sm:px-5"
    >
      <div className="flex items-start gap-3">
        <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-indigo-600 dark:text-indigo-300" />
        <div className="min-w-0 flex-1">
          <p className="font-semibold text-[var(--aal-ink)]">
            {result.replanned ? 'Remaining weeks updated' : 'Nothing needed changing'}
          </p>
          <p className="mt-1 text-sm leading-relaxed text-[var(--aal-muted)]">
            {result.message}
          </p>

          {summary.length ? (
            <ul className="mt-3 space-y-1.5">
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
                onClick={() => setShowDetail((open) => !open)}
                className="mt-3 inline-flex items-center gap-1.5 text-xs font-medium text-indigo-600 transition hover:text-indigo-500 dark:text-indigo-300"
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

        {onDismiss ? (
          <button
            type="button"
            onClick={onDismiss}
            aria-label="Dismiss"
            className="shrink-0 rounded-lg p-1 text-[var(--aal-muted)] transition hover:bg-[var(--aal-accent-soft)] hover:text-[var(--aal-ink)]"
          >
            <X className="h-4 w-4" />
          </button>
        ) : null}
      </div>
    </motion.div>
  )
}
