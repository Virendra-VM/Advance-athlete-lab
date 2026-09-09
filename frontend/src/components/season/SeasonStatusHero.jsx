import { Flag } from 'lucide-react'
import {
  countdownLabel,
  formatSeasonDate,
  phaseAccent,
  phaseGuide,
  phaseLabel,
  todayPositionPct,
} from '../../utils/seasonGuides'

/**
 * One glance: goal race, current phase, countdown, primary action.
 */
export default function SeasonStatusHero({
  aRace,
  raceDays,
  currentPhase,
  weekInPhase,
  seasonStart,
  seasonEnd,
  hasPlan,
}) {
  const progress =
    hasPlan && seasonStart && seasonEnd
      ? todayPositionPct(seasonStart, seasonEnd)
      : null
  const phase = currentPhase ? phaseGuide(currentPhase.phase_type) : null
  const accent = currentPhase ? phaseAccent(currentPhase.phase_type) : null

  return (
    <div className="overflow-hidden rounded-2xl border border-[var(--aal-line)] bg-[var(--aal-card)]">
      <div
        className="relative px-4 py-4 sm:px-5 sm:py-5"
        style={{
          background:
            'radial-gradient(100% 120% at 0% 0%, rgba(55,48,163,0.12), transparent 50%), linear-gradient(180deg, color-mix(in srgb, var(--aal-card) 92%, #312e81), var(--aal-card))',
        }}
      >
        <div className="grid gap-4 lg:grid-cols-[1fr_auto_auto] lg:items-center">
          {/* Goal */}
          <div className="flex min-w-0 items-start gap-3">
            <div className="shrink-0 rounded-xl bg-indigo-600/15 p-2.5 text-indigo-600 dark:text-indigo-300">
              <Flag className="h-5 w-5" />
            </div>
            <div className="min-w-0">
              <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-indigo-500 dark:text-indigo-300">
                Goal race
              </p>
              <h2 className="mt-0.5 truncate text-xl font-bold text-[var(--aal-ink)] sm:text-2xl">
                {aRace?.name}
              </h2>
              <p className="mt-0.5 text-sm text-[var(--aal-muted)]">
                {formatSeasonDate(aRace?.date)}
                {aRace?.target_metric ? ` · Target ${aRace.target_metric}` : ''}
              </p>
            </div>
          </div>

          {/* Current phase */}
          {hasPlan && currentPhase && phase && accent ? (
            <div
              className={`rounded-xl border px-4 py-3 lg:min-w-[12rem] ${accent.ring} bg-[var(--aal-card)]/80`}
            >
              <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[var(--aal-muted)]">
                You are here
              </p>
              <p className="mt-0.5 flex flex-wrap items-baseline gap-x-2">
                <span className="text-lg font-bold text-[var(--aal-ink)]">
                  {phaseLabel(currentPhase.phase_type)}
                </span>
                {weekInPhase ? (
                  <span className="text-sm font-medium text-[var(--aal-muted)]">
                    Week {weekInPhase} of {currentPhase.week_count}
                  </span>
                ) : null}
              </p>
              <p className="mt-0.5 text-xs text-[var(--aal-muted)]">{phase.tagline}</p>
            </div>
          ) : null}

          {/* Countdown */}
          <div className="flex items-center gap-3 rounded-xl border border-indigo-500/20 bg-[var(--aal-card)]/80 px-4 py-2.5">
            <div className="text-center">
              <p className="text-3xl font-bold tabular-nums leading-none text-indigo-600 dark:text-indigo-300">
                {raceDays != null && raceDays >= 0 ? raceDays : '—'}
              </p>
              <p className="mt-0.5 text-[10px] font-semibold uppercase tracking-[0.12em] text-[var(--aal-muted)]">
                days left
              </p>
            </div>
            <p className="max-w-[8rem] text-xs leading-snug text-[var(--aal-muted)]">
              {countdownLabel(aRace?.date)}
            </p>
          </div>
        </div>

        {progress != null ? (
          <div className="mt-4">
            <div className="mb-1 flex items-center justify-between text-[10px] font-medium uppercase tracking-[0.12em] text-[var(--aal-muted)]">
              <span>Season progress</span>
              <span>{Math.round(progress)}% to race day</span>
            </div>
            <div className="h-1.5 overflow-hidden rounded-full bg-[var(--aal-line)]">
              <div
                className="h-full rounded-full bg-gradient-to-r from-indigo-500 to-indigo-400 transition-all duration-500"
                style={{ width: `${Math.min(100, Math.max(0, progress))}%` }}
              />
            </div>
          </div>
        ) : null}
      </div>
    </div>
  )
}
