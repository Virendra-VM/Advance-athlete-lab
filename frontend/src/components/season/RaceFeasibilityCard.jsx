import { Link } from 'react-router-dom'
import { Target } from 'lucide-react'
import { feasibilityGuide } from '../../utils/seasonGuides'

/**
 * A read on the A-race target, projected from the last completed B-race with
 * the Riegel formula. The engine already computed this to decide how aggressive
 * Peak should be; showing it means the athlete finds out their goal time is a
 * stretch now rather than at 30 km on race day.
 *
 * This never changes the timeline. It is a comment on the target, not the plan.
 */
export default function RaceFeasibilityCard({ feasibility, aRace }) {
  if (!feasibility) return null

  const guide = feasibilityGuide(feasibility.feasibility)
  const target = aRace?.target_metric

  return (
    <div className={`rounded-2xl border px-4 py-4 sm:px-5 ${guide.accent}`}>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex items-start gap-3">
          <Target className="mt-0.5 h-5 w-5 shrink-0" />
          <div className="min-w-0">
            <p className="flex flex-wrap items-center gap-2 font-semibold">
              Race-time check
              <span
                className={`rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide ${guide.chip}`}
              >
                {guide.label}
              </span>
            </p>
            <p className="mt-1.5 text-sm leading-relaxed opacity-90">{guide.plain}</p>
            {feasibility.peak_pace_note ? (
              <p className="mt-1.5 text-xs leading-relaxed opacity-80">
                {feasibility.peak_pace_note}
              </p>
            ) : null}
          </div>
        </div>

        <dl className="flex shrink-0 gap-4 sm:flex-col sm:gap-2 sm:text-right">
          <div>
            <dt className="text-[10px] font-semibold uppercase tracking-[0.14em] opacity-70">
              Projected
            </dt>
            <dd className="text-lg font-bold tabular-nums">
              {feasibility.predicted_a_time || '—'}
            </dd>
          </div>
          <div>
            <dt className="text-[10px] font-semibold uppercase tracking-[0.14em] opacity-70">
              Your target
            </dt>
            <dd className="text-lg font-bold tabular-nums">{target || '—'}</dd>
          </div>
        </dl>
      </div>

      <p className="mt-3 border-t border-current/15 pt-2.5 text-xs opacity-75">
        Projected from your{' '}
        <span className="font-medium">{feasibility.b_race || 'last B-race'}</span> result.
        {target ? null : (
          <>
            {' '}
            <Link to="/profile#profile-training" className="font-medium underline">
              Add a target time
            </Link>{' '}
            to see how close you are.
          </>
        )}
      </p>
    </div>
  )
}
