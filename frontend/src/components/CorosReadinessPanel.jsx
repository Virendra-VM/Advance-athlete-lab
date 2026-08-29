import MetricCard from './ui/MetricCard'

function formatMinutes(value) {
  if (value == null || Number.isNaN(Number(value))) return '—'
  const total = Math.round(Number(value))
  const hours = Math.floor(total / 60)
  const minutes = total % 60
  if (hours <= 0) return `${minutes} min`
  return `${hours}h ${minutes}m`
}

function formatNumber(value, digits = 0, suffix = '') {
  if (value == null || Number.isNaN(Number(value))) return '—'
  return `${Number(value).toFixed(digits)}${suffix}`
}

export default function CorosReadinessPanel({ health, fitness }) {
  const recoveryPct = fitness?.recovery_pct
  const recoveryLevel = fitness?.recovery_level
  const recoveryFull = fitness?.recovery_full_at

  return (
    <section className="space-y-4">
      <div>
        <h2 className="text-2xl font-bold text-slate-900 dark:text-white">COROS Readiness</h2>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          Sleep, HRV, stress, RHR, and recovery from your COROS account.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        <MetricCard
          label="Recovery"
          value={formatNumber(recoveryPct, 0, '%')}
          subtitle={[recoveryLevel, recoveryFull ? `Full: ${recoveryFull}` : null]
            .filter(Boolean)
            .join(' · ') || 'Latest recovery status'}
        />
        <MetricCard
          label="Sleep score"
          value={formatNumber(health?.sleep_score, 0)}
          subtitle={`${formatMinutes(health?.sleep_duration_min)} total`}
        />
        <MetricCard
          label="HRV"
          value={formatNumber(health?.hrv, 0, ' ms')}
          subtitle={health?.hrv_assessment || 'Sleep HRV assessment'}
        />
        <MetricCard
          label="Stress"
          value={formatNumber(health?.stress, 0)}
          subtitle="Daily average stress"
        />
        <MetricCard
          label="Resting HR"
          value={formatNumber(health?.resting_heart_rate, 0, ' bpm')}
          subtitle="Resting heart rate"
        />
        <MetricCard
          label="Sleep stages"
          value={
            health
              ? `${formatNumber(health.deep_sleep_pct, 0)}/${formatNumber(health.light_sleep_pct, 0)}/${formatNumber(health.rem_sleep_pct, 0)}`
              : '—'
          }
          subtitle="Deep / Light / REM %"
        />
      </div>
    </section>
  )
}
