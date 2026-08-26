import { formatDistanceKm } from '../../utils/formatters'
import { formatLapDuration, formatPace } from './detailFormatters'
import ScrollableTable, { stickyTheadClass } from '../ui/ScrollableTable'

export default function LapsTable({ laps = [], mode = 'run' }) {
  if (!laps.length) return null

  const isRide = mode === 'ride'
  const isSwim = mode === 'swim'
  const isRun = mode === 'run' || mode === 'endurance'

  return (
    <div className="overflow-hidden rounded-xl border border-[var(--aal-line)]">
      <ScrollableTable autoHeight bottomOffset={24}>
        <table className="min-w-full text-left text-sm">
          <thead className={stickyTheadClass}>
            <tr>
              <th className="whitespace-nowrap px-3 py-2 font-semibold">Lap</th>
              <th className="whitespace-nowrap px-3 py-2 font-semibold">Distance</th>
              <th className="whitespace-nowrap px-3 py-2 font-semibold">Time</th>
              <th className="whitespace-nowrap px-3 py-2 font-semibold">Total Time</th>
              {isRide ? (
                <th className="whitespace-nowrap px-3 py-2 font-semibold">Avg. Speed</th>
              ) : null}
              {isRun ? (
                <th className="whitespace-nowrap px-3 py-2 font-semibold">Avg. Pace</th>
              ) : null}
              <th className="whitespace-nowrap px-3 py-2 font-semibold">Avg. HR</th>
              {isRide ? (
                <th className="whitespace-nowrap px-3 py-2 font-semibold">Effort Accuracy</th>
              ) : null}
              {isRide ? (
                <th className="whitespace-nowrap px-3 py-2 font-semibold">Avg. Power</th>
              ) : null}
              {(isRide || isRun) ? (
                <th className="whitespace-nowrap px-3 py-2 font-semibold">Max Heart Rate</th>
              ) : null}
              {isRide ? (
                <th className="whitespace-nowrap px-3 py-2 font-semibold">Avg. Cadence</th>
              ) : null}
              {isRide ? (
                <th className="whitespace-nowrap px-3 py-2 font-semibold">NP</th>
              ) : null}
              {isSwim ? (
                <th className="whitespace-nowrap px-3 py-2 font-semibold">Strokes</th>
              ) : null}
              {isSwim ? (
                <th className="whitespace-nowrap px-3 py-2 font-semibold">SWOLF</th>
              ) : null}
              {isRun ? (
                <th className="whitespace-nowrap px-3 py-2 font-semibold">Cadence</th>
              ) : null}
            </tr>
          </thead>
          <tbody className="bg-[var(--aal-card)]">
            {laps.map((lap) => {
              const pace =
                lap.avg_pace != null
                  ? formatPace(lap.avg_pace)
                  : lap.distance_m > 0 && lap.duration_s > 0
                    ? formatPace(lap.duration_s / 60 / (lap.distance_m / 1000))
                    : '—'
              const speed =
                lap.avg_speed != null
                  ? Number(lap.avg_speed).toFixed(1)
                  : lap.distance_m > 0 && lap.duration_s > 0
                    ? ((lap.distance_m / lap.duration_s) * 3.6).toFixed(1)
                    : null

              return (
                <tr
                  key={`${lap.index}-${lap.label}`}
                  className="border-t border-[var(--aal-line)]"
                >
                  <td className="whitespace-nowrap px-3 py-2 font-medium">
                    {lap.label || `Lap ${lap.index}`}
                  </td>
                  <td className="whitespace-nowrap px-3 py-2 tabular-nums">
                    {lap.distance_m != null
                      ? isSwim && lap.distance_m < 1000
                        ? `${Math.round(lap.distance_m)} m`
                        : formatDistanceKm(lap.distance_m)
                      : '—'}
                  </td>
                  <td className="whitespace-nowrap px-3 py-2 tabular-nums">
                    {formatLapDuration(lap.duration_s)}
                  </td>
                  <td className="whitespace-nowrap px-3 py-2 tabular-nums">
                    {formatLapDuration(lap.total_time_s ?? lap.duration_s)}
                  </td>
                  {isRide ? (
                    <td className="whitespace-nowrap px-3 py-2 tabular-nums">
                      {speed != null ? (
                        <>
                          {speed}
                          <span className="ml-1 text-xs text-[var(--aal-muted)]">km/h</span>
                        </>
                      ) : (
                        '—'
                      )}
                    </td>
                  ) : null}
                  {isRun ? (
                    <td className="whitespace-nowrap px-3 py-2 tabular-nums">
                      {pace}
                      {pace !== '—' ? (
                        <span className="ml-1 text-xs text-[var(--aal-muted)]">/km</span>
                      ) : null}
                    </td>
                  ) : null}
                  <td className="whitespace-nowrap px-3 py-2 tabular-nums">
                    {lap.avg_hr != null ? Math.round(lap.avg_hr) : '—'}
                    {lap.avg_hr != null ? (
                      <span className="ml-1 text-xs text-[var(--aal-muted)]">bpm</span>
                    ) : null}
                  </td>
                  {isRide ? (
                    <td className="whitespace-nowrap px-3 py-2 tabular-nums">
                      {lap.effort_accuracy ?? '—'}
                    </td>
                  ) : null}
                  {isRide ? (
                    <td className="whitespace-nowrap px-3 py-2 tabular-nums">
                      {lap.avg_power != null ? Math.round(lap.avg_power) : '—'}
                      {lap.avg_power != null ? (
                        <span className="ml-1 text-xs text-[var(--aal-muted)]">W</span>
                      ) : null}
                    </td>
                  ) : null}
                  {isRide || isRun ? (
                    <td className="whitespace-nowrap px-3 py-2 tabular-nums">
                      {lap.max_hr != null ? Math.round(lap.max_hr) : '—'}
                      {lap.max_hr != null ? (
                        <span className="ml-1 text-xs text-[var(--aal-muted)]">bpm</span>
                      ) : null}
                    </td>
                  ) : null}
                  {isRide ? (
                    <td className="whitespace-nowrap px-3 py-2 tabular-nums">
                      {lap.avg_cadence != null ? Math.round(lap.avg_cadence) : '—'}
                      {lap.avg_cadence != null ? (
                        <span className="ml-1 text-xs text-[var(--aal-muted)]">rpm</span>
                      ) : null}
                    </td>
                  ) : null}
                  {isRide ? (
                    <td className="whitespace-nowrap px-3 py-2 tabular-nums">
                      {lap.normalized_power != null ? Math.round(lap.normalized_power) : '—'}
                      {lap.normalized_power != null ? (
                        <span className="ml-1 text-xs text-[var(--aal-muted)]">W</span>
                      ) : null}
                    </td>
                  ) : null}
                  {isSwim ? (
                    <td className="whitespace-nowrap px-3 py-2 tabular-nums">
                      {lap.stroke_count ?? '—'}
                    </td>
                  ) : null}
                  {isSwim ? (
                    <td className="whitespace-nowrap px-3 py-2 tabular-nums">
                      {lap.swolf != null ? Math.round(lap.swolf) : '—'}
                    </td>
                  ) : null}
                  {isRun ? (
                    <td className="whitespace-nowrap px-3 py-2 tabular-nums">
                      {lap.avg_cadence != null ? Math.round(lap.avg_cadence) : '—'}
                      {lap.avg_cadence != null ? (
                        <span className="ml-1 text-xs text-[var(--aal-muted)]">spm</span>
                      ) : null}
                    </td>
                  ) : null}
                </tr>
              )
            })}
          </tbody>
        </table>
      </ScrollableTable>
    </div>
  )
}
