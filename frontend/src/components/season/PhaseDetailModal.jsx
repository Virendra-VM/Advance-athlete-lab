import { useEffect, useId, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import {
  CalendarDays,
  ChevronLeft,
  ChevronRight,
  Flag,
  Minus,
  Plus,
  RefreshCw,
  Trash2,
  X,
} from 'lucide-react'
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
  onShiftRecovery,
  onDeletePhase,
  onReplacePhase,
  onPlanRecoveryWeek,
  onClose,
  onNavigate,
}) {
  const titleId = useId()
  const open = index != null && phases[index] != null
  const [shiftDate, setShiftDate] = useState('')
  const [replaceType, setReplaceType] = useState('')
  const [guideOpen, setGuideOpen] = useState(false)

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

  useEffect(() => {
    if (!phase?.start_date) {
      setShiftDate('')
      return
    }
    setShiftDate(phase.start_date)
    setReplaceType(phase.phase_type)
    setGuideOpen(false)
  }, [phase?.id, phase?.start_date, phase?.phase_type])
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

            <div className="space-y-4 px-5 py-4 sm:px-6">
              <p className="text-sm leading-snug text-[var(--aal-muted)]">{guide.why}</p>

              <div className="grid gap-2 sm:grid-cols-3">
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

              {(onReplacePhase || onAdjustWeeks || onDeletePhase || onShiftRecovery) &&
              (phase.can_replace || phase.can_grow || phase.can_shrink || phase.can_delete) ? (
                <div className="rounded-xl border border-indigo-500/25 bg-indigo-500/5 px-3 py-3">
                  <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-indigo-500 dark:text-indigo-300">
                    Edit this block
                  </p>
                  <p className="mt-1 text-xs leading-relaxed text-[var(--aal-muted)]">
                    Replace the block type, change length, remove a single week, or move a recovery
                    week. Taper, restore, and finished weeks stay fixed — your A-race date does not
                    move.
                  </p>

                  {onReplacePhase && phase.can_replace ? (
                    <div className="mt-3 flex flex-col gap-2 sm:flex-row sm:items-end">
                      <label className="flex min-w-0 flex-1 flex-col gap-1">
                        <span className="text-[10px] font-semibold uppercase tracking-[0.12em] text-[var(--aal-muted)]">
                          Replace as
                        </span>
                        <select
                          value={replaceType}
                          disabled={adjusting}
                          onChange={(event) => setReplaceType(event.target.value)}
                          className="rounded-xl border border-[var(--aal-line)] bg-[var(--aal-card)] px-3 py-2 text-sm text-[var(--aal-ink)]"
                        >
                          <option value="base">Base</option>
                          <option value="build">Build</option>
                          <option value="peak">Peak</option>
                          <option value="recovery_week">Recovery week</option>
                        </select>
                      </label>
                      <button
                        type="button"
                        disabled={
                          adjusting || !replaceType || replaceType === phase.phase_type
                        }
                        onClick={() => onReplacePhase(phase.id, replaceType)}
                        className="inline-flex shrink-0 items-center justify-center gap-1.5 rounded-xl bg-indigo-600 px-3 py-2 text-xs font-semibold text-white transition hover:bg-indigo-500 disabled:opacity-40"
                      >
                        <RefreshCw className="h-3.5 w-3.5" />
                        {adjusting ? 'Replacing…' : 'Replace block'}
                      </button>
                    </div>
                  ) : null}

                  {onAdjustWeeks ? (
                    <div className="mt-3 flex flex-wrap items-center gap-2">
                      <button
                        type="button"
                        onClick={() => onAdjustWeeks(phase.id, -1)}
                        disabled={adjusting || !phase.can_shrink}
                        className="inline-flex items-center gap-1.5 rounded-xl border border-[var(--aal-line)] bg-[var(--aal-card)] px-3 py-1.5 text-xs font-semibold text-[var(--aal-ink)] transition hover:border-indigo-300 disabled:opacity-40"
                      >
                        <Minus className="h-3.5 w-3.5" />
                        Shorter
                      </button>
                      <button
                        type="button"
                        onClick={() => onAdjustWeeks(phase.id, 1)}
                        disabled={adjusting || !phase.can_grow}
                        className="inline-flex items-center gap-1.5 rounded-xl border border-[var(--aal-line)] bg-[var(--aal-card)] px-3 py-1.5 text-xs font-semibold text-[var(--aal-ink)] transition hover:border-indigo-300 disabled:opacity-40"
                      >
                        <Plus className="h-3.5 w-3.5" />
                        Longer
                      </button>
                      {phase.week_count === 1 && phase.can_delete && onDeletePhase ? (
                        <>
                          <button
                            type="button"
                            disabled={adjusting}
                            onClick={() => onDeletePhase(phase.id, 'prev')}
                            className="inline-flex items-center gap-1.5 rounded-xl border border-red-500/30 bg-red-500/10 px-3 py-1.5 text-xs font-semibold text-red-700 transition hover:bg-red-500/15 disabled:opacity-40 dark:text-red-200"
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                            Remove · merge prev
                          </button>
                          <button
                            type="button"
                            disabled={adjusting}
                            onClick={() => onDeletePhase(phase.id, 'next')}
                            className="inline-flex items-center gap-1.5 rounded-xl border border-red-500/30 bg-red-500/10 px-3 py-1.5 text-xs font-semibold text-red-700 transition hover:bg-red-500/15 disabled:opacity-40 dark:text-red-200"
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                            Remove · merge next
                          </button>
                        </>
                      ) : null}
                    </div>
                  ) : null}

                  {phase.phase_type === 'recovery_week' && onShiftRecovery ? (
                    <div className="mt-3 flex flex-col gap-2 sm:flex-row sm:items-end">
                      <label className="flex min-w-0 flex-1 flex-col gap-1">
                        <span className="text-[10px] font-semibold uppercase tracking-[0.12em] text-[var(--aal-muted)]">
                          Move to week starting
                        </span>
                        <input
                          type="date"
                          value={shiftDate}
                          disabled={adjusting}
                          onChange={(event) => setShiftDate(event.target.value)}
                          className="rounded-xl border border-[var(--aal-line)] bg-[var(--aal-card)] px-3 py-2 text-sm text-[var(--aal-ink)]"
                        />
                      </label>
                      <button
                        type="button"
                        disabled={adjusting || !shiftDate || shiftDate === phase.start_date}
                        onClick={() => onShiftRecovery(phase.id, shiftDate)}
                        className="inline-flex shrink-0 items-center justify-center rounded-xl border border-sage/40 bg-sage/10 px-3 py-2 text-xs font-semibold text-sage transition hover:bg-sage/20 disabled:opacity-40"
                      >
                        {adjusting ? 'Moving…' : 'Move week'}
                      </button>
                    </div>
                  ) : null}

                  {onPlanRecoveryWeek && phase.phase_type === 'recovery_week' ? (
                    <button
                      type="button"
                      onClick={() => onPlanRecoveryWeek(phase)}
                      className="mt-3 inline-flex items-center gap-1.5 text-xs font-semibold text-sage transition hover:underline"
                    >
                      Ask coach about timing
                    </button>
                  ) : null}

                  {adjustError ? (
                    <p className="mt-2 text-xs text-danger-muted">{adjustError}</p>
                  ) : null}
                </div>
              ) : null}

              <button
                type="button"
                onClick={() => setGuideOpen((current) => !current)}
                className="flex w-full items-center justify-between rounded-xl border border-[var(--aal-line)] px-3 py-2.5 text-left text-sm font-semibold text-[var(--aal-ink)] transition hover:border-indigo-300/50"
              >
                Phase guide
                <span className="text-xs font-medium text-indigo-500">
                  {guideOpen ? 'Hide' : 'Show'}
                </span>
              </button>

              {guideOpen ? (
                <div className="space-y-3 rounded-xl border border-[var(--aal-line)] bg-[var(--aal-bg)]/30 px-3 py-3">
                  <div>
                    <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-indigo-500 dark:text-indigo-300">
                      Focus
                    </p>
                    <ul className="mt-1.5 space-y-1">
                      {guide.focus.map((item) => (
                        <li key={item} className="text-xs leading-snug text-[var(--aal-ink)]/85">
                          {item}
                        </li>
                      ))}
                    </ul>
                  </div>
                  <div>
                    <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[var(--aal-muted)]">
                      Avoid
                    </p>
                    <ul className="mt-1.5 space-y-1">
                      {guide.avoid.map((item) => (
                        <li key={item} className="text-xs leading-snug text-[var(--aal-muted)]">
                          {item}
                        </li>
                      ))}
                    </ul>
                  </div>
                  <p className="text-xs leading-relaxed text-[var(--aal-muted)]">
                    <span className="font-semibold text-[var(--aal-ink)]/80">Science. </span>
                    {guide.science}
                  </p>
                </div>
              ) : null}

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
