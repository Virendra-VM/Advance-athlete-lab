import { ArrowRight } from 'lucide-react'
import {
  formatMinutes,
  formatSeasonDate,
  intensityLabel,
  volumeBiasLabel,
} from '../../utils/seasonGuides'

function FocusMetric({ label, value, sub }) {
  return (
    <div className="min-w-0 flex-1 rounded-xl border border-[var(--aal-line)] bg-[var(--aal-card)] px-3 py-2.5">
      <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-[var(--aal-muted)]">
        {label}
      </p>
      <p className="mt-0.5 truncate text-base font-bold text-[var(--aal-ink)]">{value}</p>
      {sub ? <p className="mt-0.5 text-[10px] text-[var(--aal-muted)]">{sub}</p> : null}
    </div>
  )
}

/**
 * Actionable “what this week wants” — sits directly under the roadmap.
 */
export default function SeasonWeekFocus({ weekIntent, onPlanWeek, weekAlreadyPlanned = false }) {
  if (!weekIntent) return null

  return (
    <div className="overflow-hidden rounded-2xl border border-indigo-500/25 bg-[var(--aal-card)]">
      <div className="border-l-4 border-indigo-500 px-4 py-4 sm:px-5">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0">
            <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-indigo-500 dark:text-indigo-300">
              This week&apos;s focus
            </p>
            <p className="mt-0.5 text-sm text-[var(--aal-muted)]">
              Week of {formatSeasonDate(weekIntent.week_start)} — how your current phase wants you
              to train
            </p>
          </div>
          {weekAlreadyPlanned ? (
            <span className="inline-flex shrink-0 items-center rounded-lg border border-sage/30 bg-sage/10 px-2.5 py-1 text-xs font-semibold text-sage">
              Week already planned
            </span>
          ) : onPlanWeek ? (
            <button
              type="button"
              onClick={onPlanWeek}
              className="inline-flex shrink-0 items-center gap-1.5 text-sm font-semibold text-indigo-600 transition hover:text-indigo-500 dark:text-indigo-300"
            >
              Build sessions in Coach
              <ArrowRight className="h-4 w-4" />
            </button>
          ) : null}
        </div>

        <div className="mt-3 flex flex-col gap-2 sm:flex-row">
          <FocusMetric
            label="Intensity"
            value={intensityLabel(weekIntent.intensity_bias)}
          />
          <FocusMetric
            label="Volume"
            value={volumeBiasLabel(weekIntent.volume_bias)}
            sub={weekIntent.volume_bias != null ? `${weekIntent.volume_bias}× phase target` : null}
          />
          <FocusMetric
            label="Longest session"
            value={formatMinutes(weekIntent.long_session_allowed_min)}
            sub="Cap for this week"
          />
        </div>

        {weekIntent.notes?.length ? (
          <ul className="mt-3 space-y-1 border-t border-[var(--aal-line)] pt-3">
            {weekIntent.notes.map((note) => (
              <li
                key={note}
                className="flex gap-2 text-sm leading-snug text-[var(--aal-ink)]/85"
              >
                <span
                  className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-indigo-500"
                  aria-hidden="true"
                />
                {note}
              </li>
            ))}
          </ul>
        ) : null}
      </div>
    </div>
  )
}
