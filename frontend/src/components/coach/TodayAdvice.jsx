import { AlertTriangle, MoonStar, RefreshCw, Zap } from 'lucide-react'
import LoadingDots from '../ui/LoadingDots'

const READINESS = {
  proceed: {
    label: 'Green light',
    icon: Zap,
    accent: 'text-sage',
    ring: 'border-sage/35 bg-sage/5',
  },
  downgrade_to_easy: {
    label: 'Keep it easy',
    icon: MoonStar,
    accent: 'text-amber-status',
    ring: 'border-amber-status/35 bg-amber-50/60 dark:bg-amber-950/20',
  },
  rest_or_mobility: {
    label: 'Rest or mobility',
    icon: MoonStar,
    accent: 'text-danger-muted',
    ring: 'border-red-300/40 bg-red-50/60 dark:bg-red-950/20',
  },
}

function formatSleep(min) {
  if (min == null || Number.isNaN(Number(min))) return null
  const hours = Number(min) / 60
  const whole = Math.floor(hours)
  const mins = Math.round((hours - whole) * 60)
  return mins ? `${whole}h ${mins}m` : `${whole}h`
}

function SignalChip({ label, value }) {
  if (value == null || value === '') return null
  return (
    <div className="min-w-[4.5rem] rounded-lg border border-[var(--aal-line)]/80 bg-[var(--aal-card)]/80 px-2.5 py-1.5">
      <p className="text-[10px] font-medium uppercase tracking-[0.12em] text-[var(--aal-muted)]">
        {label}
      </p>
      <p className="mt-0.5 text-sm font-semibold tabular-nums text-[var(--aal-ink)]">{value}</p>
    </div>
  )
}

export default function TodayAdvice({
  advice,
  loading,
  error,
  onRefresh,
  refreshing,
  compact = false,
  health = null,
  fitness = null,
}) {
  if (loading) {
    return (
      <section
        className={`rounded-2xl border border-[var(--aal-line)] bg-[var(--aal-card)] ${
          compact ? 'px-4 py-3' : 'p-5 sm:p-6'
        }`}
      >
        <LoadingDots label="Reading today's signals…" />
      </section>
    )
  }

  if (error) {
    return (
      <section
        className={`rounded-2xl border border-[var(--aal-line)] bg-[var(--aal-card)] ${
          compact ? 'px-4 py-3' : 'p-5 sm:p-6'
        }`}
      >
        <p className="text-sm text-danger-muted">{error}</p>
      </section>
    )
  }

  if (!advice) return null

  const readiness = READINESS[advice.readiness?.action] || READINESS.proceed
  const Icon = readiness.icon
  const body = advice.advice || {}

  if (compact) {
    const sleep = formatSleep(health?.sleep_duration_min)
    return (
      <section className={`rounded-2xl border px-4 py-3.5 sm:px-5 ${readiness.ring}`}>
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div className="flex items-center gap-2">
            <Icon className={`h-4 w-4 shrink-0 ${readiness.accent}`} />
            <p className={`text-[11px] font-semibold uppercase tracking-[0.16em] ${readiness.accent}`}>
              Today · {readiness.label}
            </p>
          </div>
          <button
            type="button"
            onClick={onRefresh}
            disabled={refreshing}
            className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--aal-line)] px-2.5 py-1 text-xs font-medium text-[var(--aal-muted)] transition hover:text-[var(--aal-ink)] disabled:opacity-60"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${refreshing ? 'sync-spin' : ''}`} />
            Refresh
          </button>
        </div>

        <h2 className="mt-2 text-lg font-bold leading-snug text-[var(--aal-ink)] sm:text-xl">
          {body.headline}
        </h2>
        {body.recommendation ? (
          <p className="mt-1.5 max-w-3xl text-sm leading-relaxed text-[var(--aal-ink)]/85">
            {body.recommendation}
          </p>
        ) : null}

        <div className="mt-3 flex flex-wrap gap-2">
          <SignalChip
            label="Sleep score"
            value={health?.sleep_score != null ? `${Math.round(health.sleep_score)}` : null}
          />
          <SignalChip label="Time asleep" value={sleep} />
          <SignalChip
            label="HRV"
            value={
              health?.hrv != null
                ? `${Math.round(health.hrv)}${health.hrv_assessment ? ` · ${health.hrv_assessment}` : ''}`
                : null
            }
          />
          <SignalChip
            label="RHR"
            value={health?.resting_heart_rate != null ? `${Math.round(health.resting_heart_rate)}` : null}
          />
          <SignalChip label="Stress" value={health?.stress != null ? `${Math.round(health.stress)}` : null} />
          <SignalChip
            label="Recovery"
            value={
              fitness?.recovery_pct != null
                ? `${Math.round(fitness.recovery_pct)}%`
                : fitness?.recovery_level || null
            }
          />
        </div>

        {body.session_adjustment ? (
          <p className="mt-3 rounded-xl border border-[var(--aal-line)] bg-[var(--aal-card)] px-3 py-2 text-sm">
            <span className="font-semibold">Today’s session: </span>
            {body.session_adjustment}
          </p>
        ) : null}

        {advice.readiness?.reason ? (
          <p className="mt-2 text-xs text-[var(--aal-muted)]">Why: {advice.readiness.reason}</p>
        ) : null}

        {body.escalate ? (
          <div className="mt-3 flex gap-2 rounded-xl border border-red-300/50 bg-red-50/80 px-3 py-2 text-sm dark:bg-red-950/30">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-danger-muted" />
            <p>
              <span className="font-semibold">See a professional. </span>
              {body.escalation_reason || 'Your symptoms need assessment before more training.'}
            </p>
          </div>
        ) : null}
      </section>
    )
  }

  const padding = 'p-5 sm:p-6'

  return (
    <section className={`rounded-2xl border ${padding} ${readiness.ring}`}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-center gap-2">
          <Icon className={`h-4 w-4 ${readiness.accent}`} />
          <p className={`text-[11px] font-semibold uppercase tracking-[0.18em] ${readiness.accent}`}>
            Today · {readiness.label}
          </p>
        </div>
        <button
          type="button"
          onClick={onRefresh}
          disabled={refreshing}
          className="inline-flex items-center gap-2 rounded-lg border border-[var(--aal-line)] px-3 py-1.5 text-xs font-medium text-[var(--aal-muted)] transition hover:text-[var(--aal-ink)] disabled:opacity-60"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${refreshing ? 'sync-spin' : ''}`} />
          Refresh
        </button>
      </div>

      <h2
        className={`mt-2 font-bold leading-tight text-[var(--aal-ink)] ${
          compact ? 'text-lg sm:text-xl' : 'text-2xl sm:text-3xl'
        }`}
      >
        {body.headline}
      </h2>
      <p className="mt-1.5 max-w-2xl text-sm text-[var(--aal-ink)]/85">{body.recommendation}</p>

      {body.session_adjustment ? (
        <p className="mt-3 rounded-xl border border-[var(--aal-line)] bg-[var(--aal-card)] px-3 py-2 text-sm">
          <span className="font-semibold">Adjustment: </span>
          {body.session_adjustment}
        </p>
      ) : null}

      {compact ? null : body.rationale ? (
        <p className="mt-3 text-sm text-[var(--aal-muted)]">{body.rationale}</p>
      ) : null}

      {advice.readiness?.reason ? (
        <p className="mt-2 text-xs text-[var(--aal-muted)]">Signal: {advice.readiness.reason}</p>
      ) : null}

      {body.escalate ? (
        <div className="mt-4 flex gap-3 rounded-xl border border-red-300/50 bg-red-50/80 px-3 py-3 text-sm dark:bg-red-950/30">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-danger-muted" />
          <p>
            <span className="font-semibold">See a professional. </span>
            {body.escalation_reason || 'Your symptoms need assessment before more training.'}
          </p>
        </div>
      ) : null}
    </section>
  )
}
