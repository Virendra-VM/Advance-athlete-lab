import { useEffect, useId } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { AlertTriangle, RefreshCw, ShieldCheck, X } from 'lucide-react'
import {
  REBUILD_GUIDE,
  REPLAN_GUIDE,
  TRIGGER_GUIDES,
  formatSeasonDate,
} from '../../utils/seasonGuides'

function TriggerList({ triggers }) {
  if (!triggers?.length) return null
  return (
    <ul className="space-y-2">
      {triggers.map((trigger) => {
        const guide = TRIGGER_GUIDES[trigger.code]
        return (
          <li
            key={trigger.code}
            className="rounded-xl border border-[var(--aal-line)] bg-[var(--aal-bg)]/40 px-3 py-2.5"
          >
            <p className="text-sm font-semibold text-[var(--aal-ink)]">
              {guide?.title || trigger.message}
            </p>
            <p className="mt-0.5 text-xs leading-relaxed text-[var(--aal-muted)]">
              {guide?.plain || trigger.message}
            </p>
          </li>
        )
      })}
    </ul>
  )
}

function Bullets({ items, tone = 'muted' }) {
  return (
    <ul className="mt-2 space-y-1.5">
      {items.map((item) => (
        <li
          key={item}
          className={`flex gap-2 text-sm leading-snug ${
            tone === 'ink' ? 'text-[var(--aal-ink)]/85' : 'text-[var(--aal-muted)]'
          }`}
        >
          <span
            className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-indigo-500/60"
            aria-hidden="true"
          />
          <span>{item}</span>
        </li>
      ))}
    </ul>
  )
}

/**
 * Confirm step for the two destructive-ish season actions.
 *
 * Rebuild archives the plan and redraws from today, so when replan triggers
 * exist we push Replan as the primary action instead.
 */
export default function SeasonActionDialog({
  mode = null,
  triggers = [],
  aRace = null,
  busy = false,
  onCancel,
  onConfirm,
  onUseReplan,
}) {
  const titleId = useId()
  const open = mode === 'rebuild' || mode === 'replan'
  const isRebuild = mode === 'rebuild'
  const hasTriggers = triggers.length > 0

  useEffect(() => {
    if (!open) return undefined
    function onKey(event) {
      if (event.key === 'Escape' && !busy) onCancel?.()
    }
    document.addEventListener('keydown', onKey)
    const previous = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', onKey)
      document.body.style.overflow = previous
    }
  }, [open, busy, onCancel])

  const guide = isRebuild ? REBUILD_GUIDE : REPLAN_GUIDE

  return (
    <AnimatePresence>
      {open ? (
        <motion.div
          className="fixed inset-0 z-[90] flex items-end justify-center bg-black/50 p-4 sm:items-center"
          onClick={() => (busy ? null : onCancel?.())}
          role="presentation"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.18 }}
        >
          <motion.div
            role="dialog"
            aria-modal="true"
            aria-labelledby={titleId}
            className="max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-2xl border border-[var(--aal-line)] bg-[var(--aal-card)] shadow-xl"
            onClick={(event) => event.stopPropagation()}
            initial={{ opacity: 0, y: 24, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 16, scale: 0.98 }}
            transition={{ duration: 0.22, ease: [0.22, 1, 0.36, 1] }}
          >
            <div className="flex items-start justify-between gap-3 border-b border-[var(--aal-line)] px-5 py-4 sm:px-6">
              <div className="flex items-start gap-3">
                <div
                  className={`shrink-0 rounded-xl p-2 ${
                    isRebuild
                      ? 'bg-amber-500/15 text-amber-700 dark:text-amber-300'
                      : 'bg-indigo-600/15 text-indigo-600 dark:text-indigo-300'
                  }`}
                >
                  {isRebuild ? (
                    <AlertTriangle className="h-5 w-5" />
                  ) : (
                    <ShieldCheck className="h-5 w-5" />
                  )}
                </div>
                <div>
                  <h2 id={titleId} className="text-lg font-bold text-[var(--aal-ink)]">
                    {guide.title}
                  </h2>
                  {aRace?.name ? (
                    <p className="mt-0.5 text-xs text-[var(--aal-muted)]">
                      Anchored to {aRace.name} on {formatSeasonDate(aRace.date)}
                    </p>
                  ) : null}
                </div>
              </div>
              <button
                type="button"
                onClick={onCancel}
                disabled={busy}
                aria-label="Close"
                className="shrink-0 rounded-lg border border-[var(--aal-line)] p-1.5 text-[var(--aal-muted)] transition hover:text-[var(--aal-ink)] disabled:opacity-50"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="space-y-4 px-5 py-5 sm:px-6">
              <p className="text-sm leading-relaxed text-[var(--aal-ink)]/90">
                {guide.consequence}
              </p>

              {isRebuild && hasTriggers ? (
                <div className="rounded-xl border border-amber-500/40 bg-amber-500/10 px-3 py-3">
                  <p className="text-sm font-semibold text-amber-800 dark:text-amber-200">
                    Replan is probably what you want
                  </p>
                  <p className="mt-1 text-xs leading-relaxed text-amber-800/90 dark:text-amber-200/90">
                    Your training has shifted, and Replan adjusts the weeks ahead while keeping the
                    weeks you already finished. Rebuild throws those away.
                  </p>
                  <TriggerListCompact triggers={triggers} />
                </div>
              ) : null}

              {!isRebuild ? (
                <>
                  <p className="text-sm leading-relaxed text-[var(--aal-muted)]">
                    {hasTriggers
                      ? REPLAN_GUIDE.reassurance
                      : 'Nothing has tripped a warning right now, so this may come back unchanged. We will still redraw the weeks ahead from your current profile and calendar.'}
                  </p>
                  {hasTriggers ? (
                    <div>
                      <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-indigo-500 dark:text-indigo-300">
                        Why we are suggesting this
                      </p>
                      <div className="mt-2">
                        <TriggerList triggers={triggers} />
                      </div>
                    </div>
                  ) : null}
                </>
              ) : (
                <>
                  <div>
                    <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-indigo-500 dark:text-indigo-300">
                      Rebuild is the right tool when
                    </p>
                    <Bullets items={REBUILD_GUIDE.useWhen} tone="ink" />
                  </div>
                  <div>
                    <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[var(--aal-muted)]">
                      What the planner will use
                    </p>
                    <Bullets items={REBUILD_GUIDE.inputs} />
                  </div>
                </>
              )}
            </div>

            <div className="flex flex-col-reverse gap-2 border-t border-[var(--aal-line)] px-5 py-4 sm:flex-row sm:justify-end sm:px-6">
              <button
                type="button"
                onClick={onCancel}
                disabled={busy}
                className="rounded-xl border border-[var(--aal-line)] px-4 py-2 text-sm font-medium text-[var(--aal-muted)] transition hover:text-[var(--aal-ink)] disabled:opacity-50"
              >
                Cancel
              </button>

              {isRebuild && hasTriggers ? (
                <>
                  <button
                    type="button"
                    onClick={onConfirm}
                    disabled={busy}
                    className="inline-flex items-center justify-center gap-2 rounded-xl border border-amber-500/40 px-4 py-2 text-sm font-semibold text-amber-800 transition hover:bg-amber-500/10 disabled:opacity-60 dark:text-amber-200"
                  >
                    <RefreshCw className={`h-4 w-4 ${busy ? 'animate-spin' : ''}`} />
                    Rebuild anyway
                  </button>
                  <button
                    type="button"
                    onClick={onUseReplan}
                    disabled={busy}
                    className="inline-flex items-center justify-center gap-2 rounded-xl bg-indigo-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-indigo-500 disabled:opacity-60"
                  >
                    <ShieldCheck className="h-4 w-4" />
                    Replan instead
                  </button>
                </>
              ) : (
                <button
                  type="button"
                  onClick={onConfirm}
                  disabled={busy}
                  className="inline-flex items-center justify-center gap-2 rounded-xl bg-indigo-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-indigo-500 disabled:opacity-60"
                >
                  <RefreshCw className={`h-4 w-4 ${busy ? 'animate-spin' : ''}`} />
                  {busy
                    ? isRebuild
                      ? 'Rebuilding…'
                      : 'Replanning…'
                    : isRebuild
                      ? 'Rebuild season'
                      : 'Replan season'}
                </button>
              )}
            </div>
          </motion.div>
        </motion.div>
      ) : null}
    </AnimatePresence>
  )
}

function TriggerListCompact({ triggers }) {
  if (!triggers?.length) return null
  return (
    <ul className="mt-2 space-y-1">
      {triggers.map((trigger) => (
        <li
          key={trigger.code}
          className="text-xs text-amber-900/85 dark:text-amber-100/85"
        >
          {TRIGGER_GUIDES[trigger.code]?.title || trigger.message}
        </li>
      ))}
    </ul>
  )
}
