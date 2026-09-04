import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Plus, Trash2 } from 'lucide-react'
import {
  createEvent,
  deleteEvent,
  completeEvent,
  listEvents,
} from '../../api/season'

const PRIORITY_OPTIONS = [
  { id: 'B', label: 'B — Simulation / tune-up' },
  { id: 'C', label: 'C — Social / hard workout' },
  { id: 'D', label: 'D — FTP / LTHR test' },
  { id: 'E', label: 'E — Other' },
]

const PRIORITY_BADGE = {
  A: 'bg-amber-500/15 text-amber-700 dark:text-amber-300',
  B: 'bg-indigo-500/15 text-indigo-700 dark:text-indigo-300',
  C: 'bg-slate-500/15 text-slate-700 dark:text-slate-300',
  D: 'bg-teal-500/15 text-teal-700 dark:text-teal-300',
  E: 'bg-slate-500/10 text-[var(--aal-muted)]',
}

function formatDate(value) {
  if (!value) return '—'
  return new Date(`${value}T12:00:00`).toLocaleDateString(undefined, {
    weekday: 'short',
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  })
}

const FIELD_CLASS =
  'mt-1 w-full min-h-[42px] rounded-xl border border-[var(--aal-line)] bg-[var(--aal-card)] px-3 py-2 text-sm leading-normal'

export default function ProfileEventsPanel({ embedded = false, inTraining = false }) {
  const [events, setEvents] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [saving, setSaving] = useState(false)
  const [form, setForm] = useState({
    name: '',
    date: '',
    priority: 'B',
    sport_type: 'run',
    target_metric: '',
  })

  useEffect(() => {
    let cancelled = false
    async function boot() {
      setLoading(true)
      setError('')
      try {
        const data = await listEvents()
        if (!cancelled) setEvents(data || [])
      } catch (err) {
        if (!cancelled) setError(err.message || 'Failed to load season events.')
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    boot()
    return () => {
      cancelled = true
    }
  }, [])

  async function reloadEvents() {
    const data = await listEvents()
    setEvents(data || [])
  }

  async function handleAdd() {
    if (!form.name.trim() || !form.date) {
      setError('Enter a race name and date.')
      return
    }
    setSaving(true)
    setError('')
    setSuccess('')
    try {
      const created = await createEvent({
        name: form.name.trim(),
        date: form.date,
        priority: form.priority,
        sport_type: form.sport_type,
        target_metric: form.target_metric.trim() || null,
      })
      setForm({ name: '', date: '', priority: 'B', sport_type: 'run', target_metric: '' })
      setSuccess(`Added ${created.name}.`)
      await reloadEvents()
    } catch (err) {
      setError(err.message || 'Failed to add event.')
    } finally {
      setSaving(false)
    }
  }

  async function handleDelete(eventId) {
    setError('')
    try {
      await deleteEvent(eventId)
      await reloadEvents()
    } catch (err) {
      setError(err.message || 'Failed to delete event.')
    }
  }

  async function handleCompleteB(event) {
    setError('')
    const raw = window.prompt(
      `Enter finish time for "${event.name}" (e.g. 42:30 or 1:30:00)`,
      event.target_metric || '',
    )
    if (raw == null || !raw.trim()) return
    try {
      const result = await completeEvent(event.id, { result_metric: raw.trim() })
      if (result.calibration?.available) {
        window.alert(
          `B-race logged. Projected A-race: ${result.calibration.predicted_a_time_formatted} (${result.calibration.a_race_feasibility}).`,
        )
      }
      await reloadEvents()
    } catch (err) {
      setError(err.message || 'Could not complete B-race.')
    }
  }

  async function handleCompleteD(event) {
    setError('')
    const isBike = String(event.sport_type || '').includes('bike')
    const raw = window.prompt(
      isBike
        ? `Enter FTP (watts) from "${event.name}"`
        : `Enter LTHR (bpm) from "${event.name}"`,
    )
    if (raw == null || !raw.trim()) return
    const value = Number(raw)
    if (Number.isNaN(value)) {
      setError('Enter a valid number.')
      return
    }
    try {
      await completeEvent(event.id, isBike ? { ftp_watts: value } : { lthr_bpm: value })
      await reloadEvents()
    } catch (err) {
      setError(err.message || 'Could not complete D-race.')
    }
  }

  const secondaryEvents = events.filter((event) => event.priority !== 'A')

  return (
    <div className={inTraining ? '' : embedded ? '' : 'mt-8 border-t border-[var(--aal-line)] pt-6'}>
      {inTraining ? (
        <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-sage/90">
              Season races
            </p>
            <p className="mt-1 text-sm text-[var(--aal-muted)]">
              A-race comes from Event & target above. Add B/C/D checkpoints for the season planner.
            </p>
          </div>
          <Link
            to="/training/season"
            className="text-sm font-semibold text-indigo-600 hover:underline dark:text-indigo-300"
          >
            Open season timeline →
          </Link>
        </div>
      ) : !embedded ? (
        <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
          <div>
            <h3 className="text-sm font-semibold uppercase tracking-[0.14em] text-indigo-500 dark:text-indigo-300">
              Season races
            </h3>
            <p className="mt-1 text-sm text-[var(--aal-muted)]">
              A-race comes from Event & target above. Add B/C/D checkpoints for the season planner.
            </p>
          </div>
          <Link
            to="/training/season"
            className="text-sm font-semibold text-indigo-600 hover:underline dark:text-indigo-300"
          >
            Open season timeline →
          </Link>
        </div>
      ) : (
        <div className="mb-4 flex justify-end">
          <Link
            to="/training/season"
            className="text-sm font-semibold text-indigo-600 hover:underline dark:text-indigo-300"
          >
            Open season timeline →
          </Link>
        </div>
      )}

      {error ? <p className="mb-3 text-sm text-danger-muted">{error}</p> : null}
      {success ? <p className="mb-3 text-sm text-sage">{success}</p> : null}

      {loading ? (
        <p className="text-sm text-[var(--aal-muted)]">Loading events…</p>
      ) : (
        <div className="space-y-2">
          {secondaryEvents.length === 0 ? (
            <p className="text-sm text-[var(--aal-muted)]">No B/C/D races yet.</p>
          ) : (
            secondaryEvents.map((event) => (
              <div
                key={event.id}
                className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-[var(--aal-line)] px-3 py-2.5"
              >
                <div className="min-w-0">
                  <span
                    className={`mr-2 rounded-full px-2 py-0.5 text-[10px] font-bold uppercase ${PRIORITY_BADGE[event.priority] || PRIORITY_BADGE.E}`}
                  >
                    {event.priority}
                  </span>
                  <span className="font-medium text-[var(--aal-ink)]">{event.name}</span>
                  {event.target_metric ? (
                    <span className="ml-2 text-xs text-[var(--aal-muted)]">{event.target_metric}</span>
                  ) : null}
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-sm text-[var(--aal-muted)]">{formatDate(event.date)}</span>
                  {event.priority === 'B' && event.status !== 'completed' ? (
                    <button
                      type="button"
                      onClick={() => handleCompleteB(event)}
                      className="rounded-lg border border-indigo-500/30 px-2 py-1 text-[11px] font-semibold text-indigo-700 dark:text-indigo-300"
                    >
                      Log result
                    </button>
                  ) : null}
                  {event.priority === 'D' && event.status !== 'completed' ? (
                    <button
                      type="button"
                      onClick={() => handleCompleteD(event)}
                      className="rounded-lg border border-teal-500/30 px-2 py-1 text-[11px] font-semibold text-teal-700 dark:text-teal-300"
                    >
                      Log result
                    </button>
                  ) : null}
                  <button
                    type="button"
                    onClick={() => handleDelete(event.id)}
                    className="rounded-lg p-1.5 text-[var(--aal-muted)] transition hover:bg-red-500/10 hover:text-red-600"
                    aria-label={`Delete ${event.name}`}
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </div>
              </div>
            ))
          )}
        </div>
      )}

      <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        <label className="block sm:col-span-2">
          <span className="text-xs font-semibold uppercase tracking-wide text-[var(--aal-muted)]">
            Name
          </span>
          <input
            value={form.name}
            onChange={(event) => setForm((prev) => ({ ...prev, name: event.target.value }))}
            className={FIELD_CLASS}
            placeholder="Local 10k tune-up"
          />
        </label>
        <label className="block">
          <span className="text-xs font-semibold uppercase tracking-wide text-[var(--aal-muted)]">
            Date
          </span>
          <input
            type="date"
            value={form.date}
            onChange={(event) => setForm((prev) => ({ ...prev, date: event.target.value }))}
            className={FIELD_CLASS}
          />
        </label>
        <label className="block">
          <span className="text-xs font-semibold uppercase tracking-wide text-[var(--aal-muted)]">
            Priority
          </span>
          <select
            value={form.priority}
            onChange={(event) => setForm((prev) => ({ ...prev, priority: event.target.value }))}
            className={FIELD_CLASS}
          >
            {PRIORITY_OPTIONS.map((option) => (
              <option key={option.id} value={option.id}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
        <div className="flex items-end">
          <button
            type="button"
            onClick={handleAdd}
            disabled={saving || !form.name.trim() || !form.date}
            className="inline-flex min-h-[42px] w-full items-center justify-center gap-2 rounded-xl bg-indigo-600 px-3 py-2 text-sm font-semibold text-white transition hover:bg-indigo-500 disabled:opacity-60"
          >
            <Plus className="h-4 w-4" />
            {saving ? 'Adding…' : 'Add race'}
          </button>
        </div>
      </div>
    </div>
  )
}
