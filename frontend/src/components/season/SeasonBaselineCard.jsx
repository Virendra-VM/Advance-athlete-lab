import { Activity, Gauge, HeartPulse, Timer } from 'lucide-react'
import {
  confidenceGuide,
  formatMinutes,
  volumeBiasLabel,
} from '../../utils/seasonGuides'

/**
 * The plan's personalised limits, with the reason for each one.
 *
 * The engine lowers phase ceilings to what the athlete's logged training
 * supports. An athlete who cannot see why their long day is capped at 2h 30m
 * will assume the app is being timid and ignore it, so every number here is
 * paired with the sentence the backend generated to justify it.
 */

function Stat({ icon: Icon, label, value, hint }) {
  return (
    <div className="rounded-xl border border-[var(--aal-line)] bg-[var(--aal-card)] px-3.5 py-3">
      <p className="inline-flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-[0.14em] text-[var(--aal-muted)]">
        <Icon className="h-3.5 w-3.5 text-indigo-500" />
        {label}
      </p>
      <p className="mt-1 text-base font-bold text-[var(--aal-ink)]">{value}</p>
      {hint ? <p className="mt-0.5 text-xs text-[var(--aal-muted)]">{hint}</p> : null}
    </div>
  )
}

export default function SeasonBaselineCard({ baseline }) {
  if (!baseline) return null

  const confidence = confidenceGuide(baseline.confidence)
  const damped = Number(baseline.volume_damp) < 1
  const lookback = baseline.lookback_weeks || 6

  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Stat
          icon={Timer}
          label="Long day up to"
          value={formatMinutes(baseline.long_session_ceiling_min)}
          hint={
            baseline.longest_session_min
              ? `Your longest was ${formatMinutes(baseline.longest_session_min)}`
              : 'No long session logged yet'
          }
        />
        <Stat
          icon={Activity}
          label="Recovery week"
          value={`Every ${baseline.recovery_cycle_weeks} weeks`}
          hint={
            baseline.recovery_cycle_weeks <= 3
              ? 'Shortened cycle'
              : 'Three loading weeks, then one down week'
          }
        />
        <Stat
          icon={Gauge}
          label="Volume"
          value={damped ? `${Math.round(baseline.volume_damp * 100)}% of target` : 'Full target'}
          hint={damped ? 'Held back for now' : volumeBiasLabel(1)}
        />
        <Stat
          icon={HeartPulse}
          label="Training on record"
          value={`${baseline.weeks_with_training} of ${lookback} wks`}
          hint={
            baseline.chronic_weekly_km
              ? `About ${baseline.chronic_weekly_km} km a week`
              : confidence.label
          }
        />
      </div>

      {baseline.notes?.length ? (
        <ul className="space-y-2">
          {baseline.notes.map((note) => (
            <li
              key={note}
              className="flex gap-2 text-sm leading-relaxed text-[var(--aal-muted)]"
            >
              <span
                aria-hidden="true"
                className="mt-[0.45rem] h-1.5 w-1.5 shrink-0 rounded-full bg-indigo-500/60"
              />
              <span>{note}</span>
            </li>
          ))}
        </ul>
      ) : null}

      <p className="rounded-lg border border-[var(--aal-line)] bg-[var(--aal-accent-soft)] px-3 py-2 text-xs leading-relaxed text-[var(--aal-muted)]">
        <span className="font-semibold text-[var(--aal-ink)]">{confidence.label}.</span>{' '}
        {confidence.plain}
      </p>
    </div>
  )
}
