import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { AlertTriangle, RefreshCw } from 'lucide-react'
import { getTodaysCall } from '../../api/coach'
import LoadingDots from '../ui/LoadingDots'

const CALL_STYLES = {
  green: {
    ring: 'border-sage/40 bg-sage/5',
    accent: 'text-sage',
    badge: 'bg-sage/15 text-sage',
  },
  amber: {
    ring: 'border-amber-status/40 bg-amber-50/50 dark:bg-amber-950/20',
    accent: 'text-amber-status',
    badge: 'bg-amber-500/15 text-amber-status',
  },
  orange: {
    ring: 'border-orange-400/40 bg-orange-50/50 dark:bg-orange-950/20',
    accent: 'text-orange-600 dark:text-orange-300',
    badge: 'bg-orange-500/15 text-orange-600 dark:text-orange-300',
  },
  red: {
    ring: 'border-red-300/45 bg-red-50/55 dark:bg-red-950/25',
    accent: 'text-danger-muted',
    badge: 'bg-red-500/15 text-danger-muted',
  },
}

function MetricChip({ label, value }) {
  if (value == null || value === '') return null
  return (
    <div className="rounded-lg border border-[var(--aal-line)]/80 bg-[var(--aal-card)]/80 px-2.5 py-1.5">
      <p className="text-[10px] font-medium uppercase tracking-[0.12em] text-[var(--aal-muted)]">
        {label}
      </p>
      <p className="mt-0.5 text-sm font-semibold tabular-nums text-[var(--aal-ink)]">{value}</p>
    </div>
  )
}

function WarningChip({ warning }) {
  const content = (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-[11px] font-semibold ${
        warning.severity === 'critical'
          ? 'bg-red-500/15 text-danger-muted'
          : 'bg-amber-500/15 text-amber-status'
      }`}
    >
      <AlertTriangle className="h-3 w-3 shrink-0" />
      {warning.message}
    </span>
  )
  if (warning.link) {
    return (
      <Link to={warning.link} className="transition hover:opacity-80">
        {content}
      </Link>
    )
  }
  return content
}

export default function TodaysCall({ compact = false, className = '' }) {
  const [call, setCall] = useState(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState('')

  const load = useCallback(async (force = false) => {
    if (force) setRefreshing(true)
    else setLoading(true)
    setError('')
    try {
      setCall(await getTodaysCall())
    } catch (err) {
      setError(err.message || 'Could not load Today’s Call.')
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }, [])

  useEffect(() => {
    let cancelled = false
    async function boot() {
      try {
        const result = await getTodaysCall()
        if (!cancelled) setCall(result)
      } catch (err) {
        if (!cancelled) setError(err.message || 'Could not load Today’s Call.')
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    boot()
    return () => {
      cancelled = true
    }
  }, [])

  if (loading && !call) {
    return (
      <section
        className={`rounded-2xl border border-[var(--aal-line)] bg-[var(--aal-card)] ${
          compact ? 'px-4 py-3' : 'p-5 sm:p-6'
        } ${className}`}
      >
        <LoadingDots label="Reading today’s signals…" />
      </section>
    )
  }

  if (error && !call) {
    return (
      <section
        className={`rounded-2xl border border-[var(--aal-line)] bg-[var(--aal-card)] ${
          compact ? 'px-4 py-3' : 'p-5 sm:p-6'
        } ${className}`}
      >
        <p className="text-sm text-danger-muted">{error}</p>
      </section>
    )
  }

  if (!call) return null

  const look = CALL_STYLES[call.color] || CALL_STYLES.amber
  const metrics = call.metrics || {}
  const hrvLine =
    metrics.hrv != null
      ? `${Math.round(metrics.hrv)} ms${
          metrics.hrv_delta_pct != null ? ` (${metrics.hrv_delta_pct > 0 ? '+' : ''}${metrics.hrv_delta_pct}%)` : ''
        }`
      : null

  if (compact) {
    return (
      <div className={`inline-flex flex-wrap items-center gap-2 ${className}`}>
        <span
          className={`inline-flex items-center gap-2 rounded-xl border px-3 py-2 text-sm font-semibold ${look.ring} ${look.accent}`}
        >
          {call.label}
        </span>
        {(call.warnings || []).slice(0, 2).map((warning) => (
          <WarningChip key={warning.code} warning={warning} />
        ))}
        <button
          type="button"
          onClick={() => load(true)}
          disabled={refreshing}
          title="Refresh Today’s Call"
          className="inline-flex items-center rounded-lg border border-[var(--aal-line)] p-2 text-[var(--aal-muted)] hover:text-[var(--aal-ink)] disabled:opacity-60"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${refreshing ? 'sync-spin' : ''}`} />
        </button>
      </div>
    )
  }

  return (
    <section className={`rounded-2xl border ${look.ring} ${compact ? 'px-4 py-3' : 'p-5 sm:p-6'} ${className}`}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className={`text-[11px] font-semibold uppercase tracking-[0.18em] ${look.accent}`}>
            Today’s Call
          </p>
          <h2 className="mt-1 text-xl font-bold leading-snug text-[var(--aal-ink)] sm:text-2xl">
            {call.label}
          </h2>
          {call.directive ? (
            <p className="mt-1 text-sm text-[var(--aal-ink)]/85">{call.directive}</p>
          ) : null}
        </div>
        <button
          type="button"
          onClick={() => load(true)}
          disabled={refreshing}
          className="inline-flex items-center gap-2 rounded-lg border border-[var(--aal-line)] px-3 py-1.5 text-xs font-medium text-[var(--aal-muted)] transition hover:text-[var(--aal-ink)] disabled:opacity-60"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${refreshing ? 'sync-spin' : ''}`} />
          Refresh
        </button>
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        <MetricChip
          label="Readiness"
          value={metrics.readiness_score != null ? `${Math.round(metrics.readiness_score)}` : null}
        />
        <MetricChip label="HRV" value={hrvLine} />
        <MetricChip
          label="Sleep"
          value={metrics.sleep_hours != null ? `${metrics.sleep_hours.toFixed(1)} h` : null}
        />
        <MetricChip
          label="ACWR"
          value={metrics.acwr != null ? Number(metrics.acwr).toFixed(2) : null}
        />
      </div>

      {call.downgrade_reasons?.length ? (
        <p className="mt-3 text-xs text-[var(--aal-muted)]">
          Adjustments: {call.downgrade_reasons.join(' · ')}
        </p>
      ) : null}

      {call.warnings?.length ? (
        <div className="mt-3 flex flex-wrap gap-2">
          {call.warnings.map((warning) => (
            <WarningChip key={warning.code} warning={warning} />
          ))}
        </div>
      ) : null}
    </section>
  )
}
