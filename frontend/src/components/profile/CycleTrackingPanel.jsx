import { useEffect, useState } from 'react'
import { logPeriodStart } from '../../api/cycle'

function CycleTrackingFields({ form, onChange, onCycleUpdate }) {
  const [periodDate, setPeriodDate] = useState('')
  const [logging, setLogging] = useState(false)
  const [logError, setLogError] = useState('')
  const showCycle =
    form.cycle_tracking_enabled ||
    form.sex === 'female' ||
    form.sex === 'other'

  async function handleLogPeriod(event) {
    event.preventDefault()
    if (!periodDate) return
    setLogging(true)
    setLogError('')
    try {
      const ctx = await logPeriodStart(periodDate)
      onCycleUpdate?.(ctx)
      setPeriodDate('')
    } catch (err) {
      setLogError(err.message || 'Could not log period start.')
    } finally {
      setLogging(false)
    }
  }

  if (!showCycle) return null

  return (
    <div className="mt-6 rounded-2xl border border-pink-300/30 bg-pink-50/40 p-4 dark:border-pink-900/30 dark:bg-pink-950/15">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-[var(--aal-ink)]">Cycle tracking (opt-in)</p>
          <p className="mt-1 text-xs leading-relaxed text-[var(--aal-muted)]">
            Phase-aware training adjustments when enabled. Never required. COROS snapshots can also
            feed period starts when synced.
          </p>
        </div>
        <label className="inline-flex items-center gap-2 text-sm font-medium text-[var(--aal-ink)]">
          <input
            type="checkbox"
            checked={Boolean(form.cycle_tracking_enabled)}
            onChange={(event) => onChange('cycle_tracking_enabled', event.target.checked)}
            className="h-4 w-4 rounded border-[var(--aal-line)] text-sage focus:ring-sage"
          />
          Enable
        </label>
      </div>

      {form.cycle_tracking_enabled ? (
        <div className="mt-4 grid gap-4 sm:grid-cols-2">
          <label className="block text-sm">
            <span className="mb-1 block text-[var(--aal-muted)]">Manual cycle length (days)</span>
            <input
              type="number"
              min={18}
              max={45}
              value={form.cycle_length_manual ?? ''}
              onChange={(event) =>
                onChange(
                  'cycle_length_manual',
                  event.target.value ? Number(event.target.value) : null,
                )
              }
              placeholder="28"
              className="w-full rounded-xl border border-[var(--aal-line)] bg-[var(--aal-card)] px-3 py-2"
            />
          </label>
          <form onSubmit={handleLogPeriod} className="block text-sm">
            <span className="mb-1 block text-[var(--aal-muted)]">Log period start</span>
            <div className="flex gap-2">
              <input
                type="date"
                value={periodDate}
                onChange={(event) => setPeriodDate(event.target.value)}
                className="min-w-0 flex-1 rounded-xl border border-[var(--aal-line)] bg-[var(--aal-card)] px-3 py-2"
              />
              <button
                type="submit"
                disabled={logging || !periodDate}
                className="rounded-xl bg-sage px-3 py-2 text-sm font-semibold text-white disabled:opacity-60"
              >
                Log
              </button>
            </div>
            {logError ? <p className="mt-1 text-xs text-danger-muted">{logError}</p> : null}
          </form>
        </div>
      ) : null}
    </div>
  )
}

export function CycleTrackingView({ form, cycleContext }) {
  if (!form.cycle_tracking_enabled) {
    return (
      <p className="text-sm text-[var(--aal-muted)]">
        Cycle tracking is off. Enable it while editing to receive phase-aware coach adjustments.
      </p>
    )
  }
  if (!cycleContext?.available) {
    return (
      <p className="text-sm text-[var(--aal-muted)]">
        {cycleContext?.message ||
          'Log a period start (or sync COROS cycle data) to activate phase detection.'}
      </p>
    )
  }
  return (
    <div className="rounded-xl border border-[var(--aal-line)] bg-[var(--aal-bg)]/40 px-3 py-2.5">
      <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-pink-600 dark:text-pink-300">
        Current phase
      </p>
      <p className="mt-1 text-sm font-semibold capitalize text-[var(--aal-ink)]">
        {cycleContext.phase?.replace('_', ' ')} · day {cycleContext.day_in_cycle}
      </p>
      {cycleContext.training_note ? (
        <p className="mt-1 text-sm text-[var(--aal-muted)]">{cycleContext.training_note}</p>
      ) : null}
    </div>
  )
}

export default CycleTrackingFields
