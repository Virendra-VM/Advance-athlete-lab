import { useEffect, useId } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { AlertTriangle, CalendarRange, CheckCircle2, Link2, X } from 'lucide-react'
import {
  TRIGGER_GUIDES,
  formatMinutes,
  formatRange,
  formatSeasonDate,
  phaseLabel,
} from '../../utils/seasonGuides'

function InfoRow({ label, value, hint }) {
  return (
    <div className="rounded-xl border border-[var(--aal-line)] bg-[var(--aal-bg)]/40 px-3 py-2.5">
      <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[var(--aal-muted)]">
        {label}
      </p>
      <p className="mt-0.5 text-sm font-semibold text-[var(--aal-ink)]">{value}</p>
      {hint ? <p className="mt-0.5 text-xs text-[var(--aal-muted)]">{hint}</p> : null}
    </div>
  )
}

function phaseSummary(sketch) {
  const counts = {}
  for (const phase of sketch || []) {
    const key = phase.phase_type
    counts[key] = (counts[key] || 0) + (phase.week_count || 1)
  }
  return Object.entries(counts).map(([type, weeks]) => ({
    type,
    weeks,
    label: phaseLabel(type),
  }))
}

export default function SeasonPlanPreviewModal({
  open = false,
  preview = null,
  mode = 'generate',
  planningNotes = '',
  onPlanningNotesChange,
  busy = false,
  loading = false,
  error = '',
  onCancel,
  onConfirm,
}) {
  const titleId = useId()
  const isRebuild = mode === 'rebuild'

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

  const summary = phaseSummary(preview?.phase_sketch)
  const baseline = preview?.baseline
  const profile = preview?.profile
  const connections = preview?.connections

  return (
    <AnimatePresence>
      {open ? (
        <motion.div
          className="fixed inset-0 z-[95] flex items-end justify-center bg-black/50 p-4 sm:items-center"
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
            className="max-h-[92vh] w-full max-w-2xl overflow-y-auto rounded-2xl border border-[var(--aal-line)] bg-[var(--aal-card)] shadow-xl"
            onClick={(event) => event.stopPropagation()}
            initial={{ opacity: 0, y: 24, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 16, scale: 0.98 }}
            transition={{ duration: 0.22, ease: [0.22, 1, 0.36, 1] }}
          >
            <div className="flex items-start justify-between gap-3 border-b border-[var(--aal-line)] px-5 py-4 sm:px-6">
              <div className="flex items-start gap-3">
                <div className="shrink-0 rounded-xl bg-indigo-600/15 p-2 text-indigo-600 dark:text-indigo-300">
                  <CalendarRange className="h-5 w-5" />
                </div>
                <div>
                  <h2 id={titleId} className="text-lg font-bold text-[var(--aal-ink)]">
                    {isRebuild ? 'Review before rebuilding' : 'Review before planning'}
                  </h2>
                  <p className="mt-0.5 text-xs text-[var(--aal-muted)]">
                    Cross-check your profile, races, and recent training. Nothing is saved until you
                    confirm.
                  </p>
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

            <div className="space-y-5 px-5 py-5 sm:px-6">
              {loading ? (
                <p className="text-sm text-[var(--aal-muted)]">Loading your season preview…</p>
              ) : null}

              {error ? (
                <p className="rounded-xl border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-700 dark:text-red-300">
                  {error}
                </p>
              ) : null}

              {preview && !loading ? (
                <>
                  {isRebuild ? (
                    <div className="rounded-xl border border-amber-500/40 bg-amber-500/10 px-3 py-3">
                      <p className="flex items-center gap-2 text-sm font-semibold text-amber-800 dark:text-amber-200">
                        <AlertTriangle className="h-4 w-4 shrink-0" />
                        Rebuild replaces your current timeline
                      </p>
                      <p className="mt-1 text-xs leading-relaxed text-amber-900/85 dark:text-amber-100/85">
                        Finished weeks will not stay on the calendar. Use Replan instead if only
                        the weeks ahead need adjusting.
                      </p>
                    </div>
                  ) : null}

                  <section>
                    <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-indigo-500 dark:text-indigo-300">
                      A-race anchor
                    </p>
                    <div className="mt-2 rounded-xl border border-indigo-500/25 bg-indigo-500/5 px-3 py-3">
                      <p className="text-base font-bold text-[var(--aal-ink)]">
                        {preview.a_race?.name}
                      </p>
                      <p className="mt-0.5 text-sm text-[var(--aal-muted)]">
                        {formatSeasonDate(preview.a_race?.date)}
                        {preview.a_race?.target_metric
                          ? ` · Target ${preview.a_race.target_metric}`
                          : ''}
                      </p>
                      <p className="mt-1 text-xs text-[var(--aal-muted)]">
                        {preview.total_weeks} weeks from {formatSeasonDate(preview.season_start)} to{' '}
                        {formatSeasonDate(preview.season_end)}
                      </p>
                    </div>
                  </section>

                  {preview.events?.length > 0 ? (
                    <section>
                      <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[var(--aal-muted)]">
                        Season races
                      </p>
                      <ul className="mt-2 space-y-1.5">
                        {preview.events.map((event) => (
                          <li
                            key={event.id}
                            className="flex flex-wrap items-baseline gap-x-2 rounded-lg border border-[var(--aal-line)] px-3 py-2 text-sm"
                          >
                            <span className="font-semibold text-[var(--aal-ink)]">
                              {event.priority}-race
                            </span>
                            <span className="text-[var(--aal-ink)]">{event.name}</span>
                            <span className="text-[var(--aal-muted)]">
                              {formatSeasonDate(event.date)}
                            </span>
                          </li>
                        ))}
                      </ul>
                    </section>
                  ) : null}

                  <section>
                    <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[var(--aal-muted)]">
                      Your profile
                    </p>
                    <div className="mt-2 grid gap-2 sm:grid-cols-2">
                      <InfoRow label="Fitness" value={profile?.fitness_level || '—'} />
                      <InfoRow
                        label="Typical week"
                        value={
                          profile?.days_per_week
                            ? `${profile.days_per_week} days`
                            : '—'
                        }
                        hint={
                          profile?.workout_duration_minutes
                            ? `~${profile.workout_duration_minutes} min sessions`
                            : null
                        }
                      />
                      <InfoRow
                        label="Connected apps"
                        value={
                          [
                            connections?.strava_connected ? 'Strava' : null,
                            connections?.coros_connected ? 'COROS' : null,
                          ]
                            .filter(Boolean)
                            .join(' · ') || 'None yet'
                        }
                        hint="Recent training comes from connected apps"
                      />
                      {profile?.active_injuries?.length ? (
                        <InfoRow
                          label="Active injuries"
                          value={profile.active_injuries.join(', ')}
                        />
                      ) : (
                        <InfoRow label="Injuries" value="None active" />
                      )}
                    </div>
                  </section>

                  {baseline ? (
                    <section>
                      <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[var(--aal-muted)]">
                        From your last {baseline.lookback_weeks || 6} weeks of training
                      </p>
                      <div className="mt-2 grid gap-2 sm:grid-cols-2">
                        <InfoRow
                          label="Long day up to"
                          value={formatMinutes(baseline.long_session_ceiling_min)}
                          hint={
                            baseline.longest_session_min
                              ? `Longest logged: ${formatMinutes(baseline.longest_session_min)}`
                              : 'No long session logged yet'
                          }
                        />
                        <InfoRow
                          label="Recovery cycle"
                          value={`Every ${baseline.recovery_cycle_weeks} weeks`}
                        />
                        {baseline.acwr != null ? (
                          <InfoRow label="Load ratio (ACWR)" value={String(baseline.acwr)} />
                        ) : null}
                        <InfoRow
                          label="Training weeks logged"
                          value={String(baseline.weeks_with_training ?? 0)}
                        />
                      </div>
                      {baseline.notes?.length ? (
                        <ul className="mt-2 space-y-1">
                          {baseline.notes.map((note) => (
                            <li key={note} className="text-xs text-[var(--aal-muted)]">
                              • {note}
                            </li>
                          ))}
                        </ul>
                      ) : null}
                    </section>
                  ) : null}

                  {summary.length ? (
                    <section>
                      <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[var(--aal-muted)]">
                        Phase sketch
                      </p>
                      <div className="mt-2 flex flex-wrap gap-2">
                        {summary.map((row) => (
                          <span
                            key={row.type}
                            className="rounded-full border border-[var(--aal-line)] bg-[var(--aal-bg)]/50 px-3 py-1 text-xs font-medium text-[var(--aal-ink)]"
                          >
                            {row.label} · {row.weeks} wk
                          </span>
                        ))}
                      </div>
                      <ul className="mt-3 max-h-40 space-y-1 overflow-y-auto text-xs text-[var(--aal-muted)]">
                        {preview.phase_sketch.map((phase, index) => (
                          <li key={`${phase.phase_type}-${phase.start_date}-${index}`}>
                            {phaseLabel(phase.phase_type)} ·{' '}
                            {formatRange(phase.start_date, phase.end_date)}
                          </li>
                        ))}
                      </ul>
                    </section>
                  ) : null}

                  {preview.warnings?.length ? (
                    <section className="rounded-xl border border-amber-500/30 bg-amber-500/10 px-3 py-3">
                      <p className="text-sm font-semibold text-amber-800 dark:text-amber-200">
                        Planner notes
                      </p>
                      <ul className="mt-1 space-y-1 text-xs text-amber-900/85 dark:text-amber-100/85">
                        {preview.warnings.map((warning) => (
                          <li key={warning}>• {warning}</li>
                        ))}
                      </ul>
                    </section>
                  ) : null}

                  {preview.triggers?.length ? (
                    <section className="rounded-xl border border-amber-500/30 bg-amber-500/10 px-3 py-3">
                      <p className="text-sm font-semibold text-amber-800 dark:text-amber-200">
                        Active signals
                      </p>
                      <ul className="mt-1 space-y-1 text-xs text-amber-900/85 dark:text-amber-100/85">
                        {preview.triggers.map((trigger) => (
                          <li key={trigger.code}>
                            • {TRIGGER_GUIDES[trigger.code]?.title || trigger.message}
                          </li>
                        ))}
                      </ul>
                    </section>
                  ) : null}

                  <section>
                    <label
                      htmlFor="season-planning-notes"
                      className="text-[10px] font-semibold uppercase tracking-[0.14em] text-indigo-500 dark:text-indigo-300"
                    >
                      More info for your coach
                    </label>
                    <p className="mt-1 text-xs text-[var(--aal-muted)]">
                      Travel, work stress, days you cannot train, or how you want this block to
                      feel. Saved to your profile and used when planning weeks.
                    </p>
                    <textarea
                      id="season-planning-notes"
                      rows={4}
                      maxLength={2000}
                      value={planningNotes}
                      onChange={(event) => onPlanningNotesChange?.(event.target.value)}
                      disabled={busy}
                      placeholder="e.g. Away 12–18 Oct, can only train mornings before work…"
                      className="mt-2 w-full rounded-xl border border-[var(--aal-line)] bg-[var(--aal-bg)]/40 px-3 py-2.5 text-sm text-[var(--aal-ink)] outline-none ring-indigo-500/30 focus:ring-2 disabled:opacity-60"
                    />
                    <p className="mt-1 text-right text-[10px] text-[var(--aal-muted)]">
                      {(planningNotes || '').length}/2000
                    </p>
                  </section>

                  <p className="flex items-start gap-2 text-xs text-[var(--aal-muted)]">
                    <Link2 className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                    Wrong race or fitness level? Update Profile first, then return here.
                  </p>
                </>
              ) : null}
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
              <button
                type="button"
                onClick={onConfirm}
                disabled={busy || loading || !preview}
                className="inline-flex items-center justify-center gap-2 rounded-xl bg-indigo-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-indigo-500 disabled:opacity-60"
              >
                <CheckCircle2 className="h-4 w-4" />
                {busy
                  ? isRebuild
                    ? 'Rebuilding…'
                    : 'Planning…'
                  : isRebuild
                    ? 'Confirm rebuild'
                    : 'Plan my season'}
              </button>
            </div>
          </motion.div>
        </motion.div>
      ) : null}
    </AnimatePresence>
  )
}
