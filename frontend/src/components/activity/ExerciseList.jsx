import { formatDuration } from '../../utils/formatters'
import { EmptyDetailState } from './detailShared'

function formatSet(set) {
  const parts = []
  if (set.reps != null) parts.push(`${set.reps} reps`)
  if (set.weight_kg != null) parts.push(`${Number(set.weight_kg).toFixed(set.weight_kg % 1 ? 1 : 0)} kg`)
  if (set.duration_s != null) parts.push(formatDuration(set.duration_s))
  if (set.rest_s != null) parts.push(`rest ${formatDuration(set.rest_s)}`)
  return parts.length ? parts.join(' · ') : '—'
}

export default function ExerciseList({ exercises = [] }) {
  if (!exercises.length) {
    return (
      <EmptyDetailState
        title="No set breakdown from COROS yet"
        body="Duration and heart rate still show above when available. Re-open this activity after a COROS sync, or pull detail again."
      />
    )
  }

  return (
    <div className="space-y-3">
      {exercises.map((exercise) => (
        <div
          key={`${exercise.index}-${exercise.name}`}
          className="rounded-xl border border-[var(--aal-line)] bg-[var(--aal-card)] p-4"
        >
          <div className="flex items-baseline justify-between gap-3">
            <h3 className="font-semibold text-[var(--aal-ink)]">
              <span className="mr-2 text-[var(--aal-muted)]">{exercise.index}.</span>
              {exercise.name}
            </h3>
            <p className="text-xs text-[var(--aal-muted)]">
              {exercise.sets?.length || 0} set{(exercise.sets?.length || 0) === 1 ? '' : 's'}
            </p>
          </div>
          {exercise.sets?.length ? (
            <ul className="mt-3 space-y-1.5">
              {exercise.sets.map((set) => (
                <li
                  key={`${exercise.index}-${set.index}`}
                  className="flex items-center justify-between gap-3 text-sm"
                >
                  <span className="text-[var(--aal-muted)]">Set {set.index}</span>
                  <span className="tabular-nums font-medium text-[var(--aal-ink)]">
                    {formatSet(set)}
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-2 text-sm text-[var(--aal-muted)]">No set details recorded.</p>
          )}
        </div>
      ))}
    </div>
  )
}
