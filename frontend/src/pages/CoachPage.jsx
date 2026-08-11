import { useEffect, useState } from 'react'
import { getCoachContext } from '../api/coros'
import AppShell from '../components/layout/AppShell'
import LoadingDots from '../components/ui/LoadingDots'
import PageHeader from '../components/ui/PageHeader'
import SectionCard from '../components/ui/SectionCard'
import StatTile from '../components/ui/StatTile'

export default function CoachPage() {
  const [context, setContext] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    getCoachContext()
      .then(setContext)
      .catch((err) => setError(err.message || 'Failed to load coach context.'))
      .finally(() => setLoading(false))
  }, [])

  const flags = context?.readiness_flags || []
  const fitness = context?.coros?.fitness
  const health = context?.coros?.latest_health

  return (
    <AppShell title="Coach">
      <PageHeader
        eyebrow="Coach"
        title="Readiness coach"
        subtitle="Rules-based readiness signals assembled for future AI workout suggestions."
      />
      {error && <p className="mb-4 text-sm text-danger-muted">{error}</p>}
      {loading && <LoadingDots label="Loading coach context…" />}
      {!loading && (
      <>
      <div className="grid gap-4 sm:grid-cols-3">
        <StatTile label="Flags" value={String(flags.length)} subtitle={flags.join(', ') || 'None'} />
        <StatTile
          label="Recovery"
          value={fitness?.recovery_pct != null ? `${Math.round(fitness.recovery_pct)}%` : '—'}
          subtitle={fitness?.recovery_level || '—'}
        />
        <StatTile
          label="Sleep / HRV"
          value={health?.sleep_score != null ? String(Math.round(health.sleep_score)) : '—'}
          subtitle={health?.hrv != null ? `HRV ${Math.round(health.hrv)} ms` : '—'}
        />
      </div>
      <div className="mt-6">
        <SectionCard title="Context payload" subtitle="Raw coach context used by future AI generation.">
          <pre className="max-h-96 overflow-auto rounded-xl bg-slate-50 p-4 text-xs dark:bg-black/30">
            {JSON.stringify(context, null, 2)}
          </pre>
        </SectionCard>
      </div>
      </>
      )}
    </AppShell>
  )
}
