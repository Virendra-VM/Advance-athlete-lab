import { Link } from 'react-router-dom'
import { useCallback, useEffect, useState } from 'react'
import { getCoachContext, getCorosOverview, startCorosSync } from '../api/coros'
import Card from './ui/Card'
import CorosFitnessPanel from './CorosFitnessPanel'
import CorosReadinessPanel from './CorosReadinessPanel'
import CorosSchedulePanel from './CorosSchedulePanel'
import CorosTrainingLoadPanel from './CorosTrainingLoadPanel'

export default function CorosDashboardSection({ refreshKey = 0 }) {
  const [overview, setOverview] = useState(null)
  const [coachFlags, setCoachFlags] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [syncing, setSyncing] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const data = await getCorosOverview()
      setOverview(data)
      if (data.connected) {
        try {
          const context = await getCoachContext()
          setCoachFlags(context.readiness_flags || [])
        } catch {
          setCoachFlags([])
        }
      } else {
        setCoachFlags([])
      }
    } catch (err) {
      setError(err.message || 'Failed to load COROS data.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load, refreshKey])

  async function handleSync() {
    setSyncing(true)
    setError('')
    try {
      await startCorosSync()
      await load()
    } catch (err) {
      setError(err.message || 'Failed to start COROS sync.')
    } finally {
      setSyncing(false)
    }
  }

  if (loading) {
    return (
      <Card className="p-6 text-sm text-slate-500 dark:text-slate-400">
        Loading COROS readiness...
      </Card>
    )
  }

  if (!overview?.connected) {
    return (
      <Card className="p-6">
        <h2 className="text-xl font-bold text-slate-900 dark:text-white">COROS readiness</h2>
        <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">
          Connect COROS to unlock sleep, HRV, stress, recovery, VO2max, official training load,
          and your training schedule in this app.
        </p>
        <Link
          to="/connect-coros"
          className="mt-4 inline-flex rounded-xl bg-slate-900 px-5 py-3 text-sm font-semibold text-white dark:bg-white dark:text-slate-900"
        >
          Connect COROS
        </Link>
      </Card>
    )
  }

  return (
    <div className="space-y-8">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-widest text-sage">COROS</p>
          <p className="text-sm text-slate-500 dark:text-slate-400">
            {overview.last_synced_at
              ? `Last synced ${new Date(overview.last_synced_at).toLocaleString()}`
              : 'Connected — run a sync to pull the latest metrics.'}
          </p>
        </div>
        <button
          type="button"
          onClick={handleSync}
          disabled={syncing || overview.sync_status?.running}
          className="rounded-xl border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-700 disabled:opacity-60 dark:border-white/10 dark:text-slate-200"
        >
          {syncing || overview.sync_status?.running ? 'Syncing...' : 'Sync COROS'}
        </button>
      </div>

      {error && <p className="text-sm text-danger-muted">{error}</p>}

      {coachFlags.length > 0 && (
        <Card className="p-4">
          <p className="text-xs font-semibold uppercase tracking-widest text-slate-500">
            Ready for AI coaching
          </p>
          <p className="mt-2 text-sm text-slate-700 dark:text-slate-300">
            Readiness signals: {coachFlags.join(', ')}
          </p>
        </Card>
      )}

      <CorosReadinessPanel health={overview.today_health} fitness={overview.fitness} />
      <CorosFitnessPanel fitness={overview.fitness} />
      <CorosTrainingLoadPanel trainingLoad={overview.training_load} />
      <CorosSchedulePanel schedule={overview.schedule} />
    </div>
  )
}
