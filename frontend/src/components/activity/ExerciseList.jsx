import { useState } from 'react'
import { ChevronDown, Dumbbell, RefreshCw } from 'lucide-react'
import { formatDuration } from '../../utils/formatters'
// Muscle heatmap is parked until product finish — keep MuscleMap.jsx for later.
// import MuscleHeatmap from './MuscleMap'

const PRIMARY = '#ef4444'

function prettyMuscle(id) {
  return String(id || '')
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase())
}

/** "10 × 40 kg", "0:30 hold", "12 reps" */
function setWork(set) {
  const bits = []
  if (set.reps != null && set.weight_kg != null) {
    const kg = Number(set.weight_kg)
    bits.push(`${set.reps} × ${kg % 1 ? kg.toFixed(1) : kg} kg`)
  } else if (set.reps != null) {
    bits.push(`${set.reps} reps`)
  } else if (set.duration_s != null) {
    bits.push(`${formatDuration(set.duration_s)} hold`)
  }
  return bits.join(' ') || '—'
}

function exerciseTotals(exercise) {
  const sets = exercise.sets || []
  let reps = 0
  let work = 0
  let volume = 0
  for (const s of sets) {
    if (s.reps != null) reps += s.reps
    if (s.duration_s != null) work += s.duration_s
    if (s.reps != null && s.weight_kg != null) volume += s.reps * Number(s.weight_kg)
  }
  return { reps, work, volume }
}

function EmptyWorkout({ onPullDetail }) {
  const [pulling, setPulling] = useState(false)
  const [pullMsg, setPullMsg] = useState('')

  async function handlePull() {
    if (!onPullDetail) return
    setPulling(true)
    setPullMsg('')
    try {
      const result = await onPullDetail()
      if (result?.exercises_found > 0) {
        setPullMsg(`Found ${result.exercises_found} exercises. Reloading…`)
      } else if (result?.ok === false) {
        setPullMsg(`Could not load set data: ${result.reason || 'unknown error'}.`)
      } else {
        setPullMsg('No exercise data found in this FIT file.')
      }
    } catch (err) {
      setPullMsg(err.message || 'Failed to fetch FIT file.')
    } finally {
      setPulling(false)
    }
  }

  return (
    <div className="flex items-start gap-3 rounded-xl border border-dashed border-[var(--aal-line)] bg-[var(--aal-card)] p-4">
      <Dumbbell className="mt-0.5 size-4 shrink-0 text-[var(--aal-muted)]" />
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium text-[var(--aal-ink)]">No set breakdown yet</p>
        <p className="mt-0.5 text-xs text-[var(--aal-muted)]">
          Pull the COROS FIT to load exercises and set details.
        </p>
        {pullMsg && <p className="mt-1.5 text-xs text-[var(--aal-muted)]">{pullMsg}</p>}
      </div>
      {onPullDetail && (
        <button
          type="button"
          onClick={handlePull}
          disabled={pulling}
          className="inline-flex shrink-0 items-center gap-1.5 rounded-lg bg-[var(--aal-accent)] px-2.5 py-1.5 text-xs font-medium text-white transition hover:opacity-90 disabled:opacity-50"
        >
          <RefreshCw className={`size-3 ${pulling ? 'animate-spin' : ''}`} />
          {pulling ? 'Pulling…' : 'Pull'}
        </button>
      )}
    </div>
  )
}

function ExerciseRow({ exercise, maxSets }) {
  const [open, setOpen] = useState(false)
  const sets = exercise.sets || []
  const setCount = sets.length
  const primary = exercise.muscles?.primary || []
  const totals = exerciseTotals(exercise)
  const barPct = maxSets ? Math.max(8, Math.round((setCount / maxSets) * 100)) : 0

  const summary =
    totals.volume > 0
      ? `${Math.round(totals.volume).toLocaleString()} kg volume`
      : totals.reps > 0
        ? `${totals.reps} reps`
        : totals.work > 0
          ? `${formatDuration(totals.work)} work`
          : ''

  return (
    <li className="overflow-hidden border-b border-[var(--aal-line)] last:border-b-0">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="flex w-full items-center gap-3 px-3 py-2.5 text-left transition hover:bg-[var(--aal-accent-soft)]"
      >
        <span className="grid size-6 shrink-0 place-items-center rounded-md bg-[var(--aal-accent-soft)] text-[11px] font-semibold tabular-nums text-[var(--aal-accent)]">
          {exercise.index}
        </span>

        <span className="min-w-0 flex-1">
          <span className="flex items-baseline gap-2">
            <span className="truncate text-sm font-semibold text-[var(--aal-ink)]">
              {exercise.name}
            </span>
            {primary.length > 0 && (
              <span className="hidden truncate text-[11px] text-[var(--aal-muted)] sm:inline">
                {primary.map(prettyMuscle).join(' · ')}
              </span>
            )}
          </span>
          {/* relative volume bar */}
          <span className="mt-1.5 block h-1 w-full overflow-hidden rounded-full bg-[var(--aal-line)]">
            <span
              className="block h-full rounded-full"
              style={{ width: `${barPct}%`, background: PRIMARY, opacity: 0.75 }}
            />
          </span>
        </span>

        <span className="shrink-0 text-right">
          <span className="block text-sm font-semibold tabular-nums text-[var(--aal-ink)]">
            {setCount}
            <span className="ml-1 text-[11px] font-normal text-[var(--aal-muted)]">sets</span>
          </span>
          {summary && (
            <span className="block text-[11px] tabular-nums text-[var(--aal-muted)]">{summary}</span>
          )}
        </span>

        <ChevronDown
          className={`size-4 shrink-0 text-[var(--aal-muted)] transition-transform ${open ? 'rotate-180' : ''}`}
        />
      </button>

      {open && setCount > 0 && (
        <div className="bg-[var(--aal-bg)] px-3 pb-3 pt-1">
          <div className="grid gap-1.5 sm:grid-cols-2 lg:grid-cols-3">
            {sets.map((set) => (
              <div
                key={`${exercise.index}-${set.index}`}
                className="flex items-center justify-between gap-2 rounded-lg border border-[var(--aal-line)] bg-[var(--aal-card)] px-2.5 py-1.5"
              >
                <span className="text-[11px] font-medium text-[var(--aal-muted)]">
                  Set {set.index}
                </span>
                <span className="text-xs font-semibold tabular-nums text-[var(--aal-ink)]">
                  {setWork(set)}
                </span>
                <span className="text-[11px] tabular-nums text-[var(--aal-muted)]">
                  {set.rest_s != null ? `rest ${formatDuration(set.rest_s)}` : '—'}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </li>
  )
}

export default function ExerciseList({ exercises = [], muscleMap: _muscleMap = null, onPullDetail }) {
  if (!exercises.length) {
    return <EmptyWorkout onPullDetail={onPullDetail} />
  }

  const totalSets = exercises.reduce((sum, ex) => sum + (ex.sets?.length || 0), 0)
  const totalReps = exercises.reduce(
    (sum, ex) => sum + (ex.sets || []).reduce((s, set) => s + (set.reps || 0), 0),
    0,
  )
  const totalVolume = exercises.reduce((sum, ex) => sum + exerciseTotals(ex).volume, 0)
  const maxSets = Math.max(...exercises.map((ex) => ex.sets?.length || 0), 1)

  const stats = [
    { label: 'Exercises', value: exercises.length },
    { label: 'Sets', value: totalSets },
    { label: 'Reps', value: totalReps || '—' },
    ...(totalVolume > 0
      ? [{ label: 'Volume', value: `${Math.round(totalVolume).toLocaleString()} kg` }]
      : []),
  ]

  return (
    <div className="space-y-3">
      {/* <MuscleHeatmap muscleMap={_muscleMap} /> — re-enable at product finish */}

      <section className="overflow-hidden rounded-xl border border-[var(--aal-line)] bg-[var(--aal-card)]">
        <header className="flex flex-wrap items-center justify-between gap-x-6 gap-y-2 border-b border-[var(--aal-line)] px-4 py-2.5">
          <h3 className="text-sm font-semibold text-[var(--aal-ink)]">Exercises</h3>
          <dl className="flex items-center gap-5">
            {stats.map((s) => (
              <div key={s.label} className="text-right">
                <dt className="text-[10px] uppercase tracking-wide text-[var(--aal-muted)]">
                  {s.label}
                </dt>
                <dd className="text-sm font-semibold tabular-nums text-[var(--aal-ink)]">
                  {s.value}
                </dd>
              </div>
            ))}
          </dl>
        </header>

        <ul className="m-0 list-none p-0">
          {exercises.map((exercise) => (
            <ExerciseRow
              key={`${exercise.index}-${exercise.name}`}
              exercise={exercise}
              maxSets={maxSets}
            />
          ))}
        </ul>
      </section>
    </div>
  )
}
