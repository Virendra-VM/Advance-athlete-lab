import { useMemo, useState } from 'react'
import { buildDistanceSplits, splitModeOptions } from '../../utils/activitySplits'
import LapsTable from './LapsTable'
import { EmptyDetailState } from './detailShared'

export default function SplitsPanel({
  family = 'run',
  laps = [],
  points = [],
}) {
  const options = useMemo(() => splitModeOptions(family), [family])
  const defaultMode = family === 'ride' ? '5km' : family === 'swim' ? 'laps' : '1km'
  const [mode, setMode] = useState(() =>
    options.some((o) => o.id === defaultMode) ? defaultMode : 'laps',
  )

  const rows = useMemo(() => {
    if (mode === 'laps') return laps
    const option = options.find((o) => o.id === mode)
    if (!option?.meters) return []
    return buildDistanceSplits(points, option.meters)
  }, [mode, laps, points, options])

  const tableMode = family === 'ride' ? 'ride' : family === 'swim' ? 'swim' : 'run'
  const selectedLabel = options.find((o) => o.id === mode)?.label || 'Laps'

  return (
    <div className="space-y-3">
      <label className="inline-flex items-center gap-2 text-sm text-[var(--aal-muted)]">
        <span className="font-medium text-[var(--aal-ink)]">Split</span>
        <select
          value={mode}
          onChange={(e) => setMode(e.target.value)}
          aria-label={`Split by ${selectedLabel}`}
          className="h-9 min-w-[8.5rem] rounded-xl border border-[var(--aal-line)] bg-[var(--aal-card)] px-3 text-sm font-medium text-[var(--aal-ink)] outline-none focus:border-sage"
        >
          {options.map((option) => (
            <option key={option.id} value={option.id}>
              {option.label}
            </option>
          ))}
        </select>
      </label>

      {rows.length ? (
        <LapsTable laps={rows} mode={tableMode} />
      ) : (
        <EmptyDetailState
          title={mode === 'laps' ? 'No lap data yet' : 'No distance splits yet'}
          body={
            mode === 'laps'
              ? 'Lap rows appear after COROS/Strava detail enrich.'
              : 'Distance splits need timeline GPS/stream distance. Sync FIT streams, then reopen this activity.'
          }
        />
      )}
    </div>
  )
}
