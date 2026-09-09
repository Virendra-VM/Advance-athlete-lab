import { useEffect, useId } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { CalendarDays, ChevronLeft, ChevronRight, Flag, Minus, Plus, X } from 'lucide-react'
import {
  PRIORITY_GUIDES,
  formatRange,
  formatSeasonDate,
  intensityLabel,
  isCurrentPhase,
  phaseAccent,
  phaseGuide,
  phaseLabel,
  toDate,
  volumeBiasLabel,
} from '../../utils/seasonGuides'

function StatBlock({ label, value, hint }) {
  return (
    <div className="rounded-xl border border-[var(--aal-line)] bg-[var(--aal-bg)]/40 px-3 py-2.5">
      <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[var(--aal-muted)]">
        {label}
      </p>
      <p className="mt-1 text-sm font-semibold text-[var(--aal-ink)]">{value}</p>
      {hint ? <p className="mt-0.5 text-[11px] text-[var(--aal-muted)]">{hint}</p> : null}
    </div>
  )
}

function eventsInsidePhase(phase, events) {
  const start = toDate(phase?.start_date)
  const end = toDate(phase?.end_date)
  if (!start || !end) return []
  return (events || []).filter((event) => {
    const on = toDate(event.date)
    return on && on >= start && on <= end
  })
}

export default function PhaseDetailModal({
  phases = [],
  index = null,
  events = [],
  weekIntent = null,
  adjusting = false,
  adjustError = '',
  onAdjustWeeks,
  onClose,
  onNavigate,
}) {
  const titleId = useId()
  const open = index != null && phases[index] != null

  useEffect(() => {
    if (!open) return undefined
    function onKey(event) {
      if (event.key === 'Escape') onClose?.()
      if (event.key === 'ArrowLeft' && index > 0) onNavigate?.(index - 1)
      if (event.key === 'ArrowRight' && index < phases.length - 1) onNavigate?.(index + 1)
    }
    document.addEventListener('keydown', onKey)
    const previous = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', onKey)
      document.body.style.overflow = previous
    }
  }, [open, index, phases.length, onClose, onNavigate])

  const phase = open ? phases[index] : null
  const guide = phase ? phaseGuide(phase.phase_type) : null
  const accent = phase ? phaseAccent(phase.phase_type) : null
  const current = phase ? isCurrentPhase(phase) : false
  const phaseEvents = phase ? eventsInsidePhase(phase, events) : []
  const showWeekNotes = current && Array.isArray(weekIntent?.notes) && weekIntent.notes.length > 0

  return (
    <AnimatePresence>
      {open ? (
        <motion.div
          className="fixed inset-0 z-[80] flex items-end justify-center bg-black/45 p-4 sm:items-center"
          onClick={onClose}
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
            className="max-h-[90vh] w-full max-w-xl overflow-y-auto rounded-2xl border border-[var(--aal-line)] bg-[var(--aal-card)] shadow-xl"
            onClick={(event) => event.stopPropagation()}
            initial={{ opacity: 0, y: 24, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 16, scale: 0.98 }}
            transition={{ duration: 0.24, ease: [0.22, 1, 0.36, 1] }}
          >
            <div className="relative overflow-hidden border-b border-[var(--aal-line)] px-5 py-4 sm:px-6">
              <div
                className="pointer-events-none absolute inset-0"
                style={{
                  background:
                    'radial-gradient(120% 90% at 0% 0%, rgba(55,48,163,0.14), transparent 55%), linear-gradient(165deg, var(--aal-card), color-mix(in srgb, #312e81 6%, var(--aal-card)))',
                }}
              />
              <div className="relative flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <span
                      className={`rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide ${accent.chip}`}
                    >
                      {phaseLabel(phase.phase_type)}
                    </span>
                    {current ? (
                      <span className="rounded-full bg-indigo-600/15 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-indigo-600 dark:text-indigo-300">
                        You are here
                      </span>
                    ) : null}
                  </div>
                  <h2
                    id={titleId}
                    className="mt-1.5 text-xl font-bold leading-tight text-[var(--aal-ink)]"
                  >
                    {guide.tagline}
                  </h2>
                  <p className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-xs text-[var(--aal-muted)]">
                    <span className="inline-flex items-center gap-1.5">
                      <CalendarDays className="h-3.5 w-3.5" />
                      {formatRange(phase.start_date, phase.end_date)}
                    </span>
                    <span aria-hidden="true">·</span>
                    <span>
                      {phase.week_count} {phase.week_count === 1 ? 'week' : 'weeks'}
                    </span>
                  </p>
                </div>
                <button
                  type="button"
                  onClick={onClose}
                  aria-label="Close phase details"
                  className="shrink-0 rounded-lg border border-[var(--aal-line)] bg-[var(--aal-card)] p-1.5 text-[var(--aal-muted)] transition hover:text-[var(--aal-ink)]"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
            </div>

            <div className="space-y-5 px-5 py-5 sm:px-6">
              <p className="text-sm leading-relaxed text-[var(--aal-ink)]/90">{guide.why}</p>

              <div className="grid gap-2.5 sm:grid-cols-3">
                <StatBlock
                  label="Volume"
                  value={volumeBiasLabel(phase.volume_bias)}
                  hint={phase.volume_bias != null ? `${phase.volume_bias}× bias` : null}
                />
                <StatBlock label="Intensity" value={intensityLabel(phase.intensity_bias)} />
                <StatBlock
                  label="Long day up to"
                  value={
                    phase.long_session_allowed_min ? `${phase.long_session_allowed_min} min` : '—'
                  }
                />
              </div>

              {onAdjustWeeks && (phase.can_grow || phase.can_shrink) ? (
                <div className="rounded-xl border border-indigo-500/25 bg-indigo-500/5 px-3 py-3">
                  <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-indigo-500 dark:text-indigo-300">
                    Move a week
                  </p>
                  <p className="mt-1 text-xs leading-relaxed text-[var(--aal-muted)]">
                    Trade a week with a later block. Your A-race date does not move, and finished
                    weeks stay as they were.
                  </p>
                  <div className="mt-3 flex flex-wrap items-center gap-2">
                    <button
                      type="button"
                      onClick={() => onAdjustWeeks(phase.id, -1)}
                      disabled={adjusting || !phase.can_shrink}
                      className="inline-flex items-center gap-1.5 rounded-xl border border-[var(--aal-line)] bg-[var(--aal-card)] px-3 py-1.5 text-xs font-semibold text-[var(--aal-ink)] transition hover:border-indigo-300 disabled:opacity-40"
                    >
                      <Minus className="h-3.5 w-3.5" />
                      One week shorter
                    </button>
                    <button
                      type="button"
                      onClick={() => onAdjustWeeks(phase.id, 1)}
                      disabled={adjusting || !phase.can_grow}
                      className="inline-flex items-center gap-1.5 rounded-xl border border-[var(--aal-line)] bg-[var(--aal-card)] px-3 py-1.5 text-xs font-semibold text-[var(--aal-ink)] transition hover:border-indigo-300 disabled:opacity-40"
                    >
                      <Plus className="h-3.5 w-3.5" />
                      One week longer
                    </button>
                    {adjusting ? (
                      <span className="text-xs text-[var(--aal-muted)]">Updating…</span>
                    ) : null}
                  </div>
                  {adjustError ? (
                    <p className="mt-2 text-xs text-danger-muted">{adjustError}</p>
                  ) : null}
                </div>
              ) : null}

              <div>
                <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-indigo-500 dark:text-indigo-300">
                  What this block is for
                </p>
                <ul className="mt-2 space-y-1.5">
                  {guide.focus.map((item) => (
                    <li
                      key={item}
                      className="flex gap-2 text-sm leading-snug text-[var(--aal-ink)]/85"
                    >
                      <span
                        className={`mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full ${accent.dot}`}
                        aria-hidden="true"
                      />
                      <span>{item}</span>
                    </li>
                  ))}
                </ul>
              </div>

              <div>
                <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[var(--aal-muted)]">
                  Common mistakes here
                </p>
                <ul className="mt-2 space-y-1.5">
                  {guide.avoid.map((item) => (
                    <li
                      key={item}
                      className="flex gap-2 text-sm leading-snug text-[var(--aal-muted)]"
                    >
                      <span
                        className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-[var(--aal-muted)]/50"
                        aria-hidden="true"
                      />
                      <span>{item}</span>
                    </li>
                  ))}
                </ul>
              </div>

              {phaseEvents.length ? (
                <div>
                  <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-indigo-500 dark:text-indigo-300">
                    Races inside this block
                  </p>
                  <div className="mt-2 space-y-2">
                    {phaseEvents.map((event) => {
                      const priority = PRIORITY_GUIDES[event.priority] || PRIORITY_GUIDES.E
                      return (
                        <div
                          key={event.id}
                          className={`rounded-xl border px-3 py-2.5 ${priority.accent}`}
                        >
                          <div className="flex flex-wrap items-center justify-between gap-2">
                            <span className="inline-flex items-center gap-2 text-sm font-semibold">
                              <Flag className="h-3.5 w-3.5" />
                              {event.name}
                            </span>
                            <span className="text-xs tabular-nums">
                              {formatSeasonDate(event.date)}
                            </span>
                          </div>
                          <p className="mt-1 text-xs opacity-80">{priority.meaning}</p>
                        </div>
                      )
                    })}
                  </div>
                </div>
              ) : null}

              {showWeekNotes ? (
                <div className="rounded-xl border border-indigo-500/25 bg-indigo-500/5 px-3 py-3">
                  <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-indigo-500 dark:text-indigo-300">
                    This week inside the block
                  </p>
                  <ul className="mt-2 space-y-1.5 text-sm leading-snug text-[var(--aal-ink)]/85">
                    {weekIntent.notes.map((note) => (
                      <li key={note}>{note}</li>
                    ))}
                  </ul>
                </div>
              ) : null}

              <p className="border-t border-[var(--aal-line)] pt-4 text-xs leading-relaxed text-[var(--aal-muted)]">
                <span className="font-semibold text-[var(--aal-ink)]/80">The science. </span>
                {guide.science}
              </p>
            </div>

            <div className="flex items-center justify-between gap-2 border-t border-[var(--aal-line)] px-5 py-3 sm:px-6">
              <button
                type="button"
                onClick={() => onNavigate?.(index - 1)}
                disabled={index <= 0}
                className="inline-flex items-center gap-1.5 rounded-xl border border-[var(--aal-line)] px-3 py-1.5 text-xs font-medium text-[var(--aal-muted)] transition hover:text-[var(--aal-ink)] disabled:opacity-40"
              >
                <ChevronLeft className="h-3.5 w-3.5" />
                {index > 0 ? phaseLabel(phases[index - 1].phase_type) : 'Previous'}
              </button>
              <span className="text-[11px] tabular-nums text-[var(--aal-muted)]">
                {index + 1} of {phases.length}
              </span>
              <button
                type="button"
                onClick={() => onNavigate?.(index + 1)}
                disabled={index >= phases.length - 1}
                className="inline-flex items-center gap-1.5 rounded-xl border border-[var(--aal-line)] px-3 py-1.5 text-xs font-medium text-[var(--aal-muted)] transition hover:text-[var(--aal-ink)] disabled:opacity-40"
              >
                {index < phases.length - 1 ? phaseLabel(phases[index + 1].phase_type) : 'Next'}
                <ChevronRight className="h-3.5 w-3.5" />
              </button>
            </div>
          </motion.div>
        </motion.div>
      ) : null}
    </AnimatePresence>
  )
}
