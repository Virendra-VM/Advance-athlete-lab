import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { RefreshCw } from 'lucide-react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import BarActiveGlow from './charts/BarActiveEffects'
import { dedupeActivities, listActivities } from '../api/activities'
import { getAthleteStats } from '../api/athlete'
import { getCorosOverview, getCorosSyncStatus, startCorosSync } from '../api/coros'
import {
  getStravaConnectionStatus,
  getStravaSyncStatus,
  startStravaSync,
} from '../api/strava'
import { useAuth } from '../context/AuthContext'
import AppShell from './layout/AppShell'
import ActivitiesTable from './ActivitiesTable'
import LoadingDots from './ui/LoadingDots'
import PageHeader from './ui/PageHeader'
import SectionCard from './ui/SectionCard'
import StatTile from './ui/StatTile'
import SyncResultModal, { buildSyncResult } from './ui/SyncResultModal'
import TodaysCall from './coach/TodaysCall'

function fmt(value, digits = 0, suffix = '') {
  if (value == null || Number.isNaN(Number(value))) return '—'
  return `${Number(value).toFixed(digits)}${suffix}`
}

export default function Dashboard() {
  const { profile } = useAuth()
  const [overview, setOverview] = useState(null)
  const [stats, setStats] = useState(null)
  const [recent, setRecent] = useState([])
  const [error, setError] = useState('')
  const [corosSyncing, setCorosSyncing] = useState(false)
  const [stravaSyncing, setStravaSyncing] = useState(false)
  const [stravaConnected, setStravaConnected] = useState(false)
  const [loading, setLoading] = useState(true)
  const [syncResult, setSyncResult] = useState(null)

  const refreshDashboard = useCallback(async () => {
    if (!profile?.id) return
    const [coros, athleteStats, activities] = await Promise.all([
      getCorosOverview().catch(() => null),
      getAthleteStats(profile.id),
      listActivities(profile.id, { page: 1, page_size: 5 }),
    ])
    setOverview(coros)
    setStats(athleteStats)
    setRecent(activities.items || [])
  }, [profile?.id])

  useEffect(() => {
    if (!profile?.id) return
    let cancelled = false
    async function load() {
      setLoading(true)
      setError('')
      try {
        const [, stravaStatus] = await Promise.all([
          refreshDashboard(),
          getStravaConnectionStatus().catch(() => ({ connected: false })),
        ])
        if (cancelled) return
        setStravaConnected(Boolean(stravaStatus.connected))
      } catch (err) {
        if (!cancelled) setError(err.message || 'Failed to load dashboard.')
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    load()
    return () => {
      cancelled = true
    }
  }, [profile?.id, refreshDashboard])

  const volumeData = useMemo(
    () =>
      (stats?.weekly_volume_history || []).map((bucket) => ({
        label: bucket.week_label,
        km: bucket.total_distance_km,
      })),
    [stats],
  )

  const loadTrend = useMemo(() => {
    const comments = overview?.training_load?.daily_comments || []
    return comments
      .slice()
      .reverse()
      .map((row) => ({
        label: String(row.date || '').slice(5),
        ratio: row.load_ratio,
      }))
      .filter((row) => row.label)
  }, [overview])

  async function handleSyncCoros() {
    setCorosSyncing(true)
    setError('')
    try {
      await startCorosSync()
      let status = null
      const started = Date.now()
      while (Date.now() - started < 120000) {
        await new Promise((resolve) => setTimeout(resolve, 1200))
        status = await getCorosSyncStatus()
        if (!status.running) break
      }
      try {
        await dedupeActivities()
      } catch {
        // non-fatal
      }
      await refreshDashboard()
      setSyncResult(buildSyncResult('coros', status || {}))
    } catch (err) {
      setError(err.message || 'COROS sync failed.')
    } finally {
      setCorosSyncing(false)
    }
  }

  async function handleSyncStrava() {
    if (!profile?.id) return
    setStravaSyncing(true)
    setError('')
    try {
      await startStravaSync()
      let status = null
      const started = Date.now()
      while (Date.now() - started < 120000) {
        await new Promise((resolve) => setTimeout(resolve, 1200))
        status = await getStravaSyncStatus()
        if (!status.running) break
      }
      try {
        await dedupeActivities()
      } catch {
        // non-fatal
      }
      await refreshDashboard()
      setSyncResult(buildSyncResult('strava', status || {}))
    } catch (err) {
      setError(err.message || 'Strava sync failed.')
    } finally {
      setStravaSyncing(false)
    }
  }

  const health = overview?.today_health
  const fitness = overview?.fitness
  const anySyncing = corosSyncing || stravaSyncing

  return (
    <AppShell title="Dashboard">
      <PageHeader
        eyebrow="Home"
        title={`Welcome back${profile?.name ? `, ${profile.name.split(' ')[0]}` : ''}`}
        subtitle="Today’s readiness, training load, and recent work — details live in each sidebar section."
        actions={
          <div className="flex flex-wrap items-center gap-2">
            {stravaConnected ? (
              <button
                type="button"
                onClick={handleSyncStrava}
                disabled={anySyncing}
                className="inline-flex items-center gap-2 rounded-xl bg-[#FC4C02] px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-60"
              >
                <RefreshCw className={`h-4 w-4 ${stravaSyncing ? 'sync-spin' : ''}`} />
                {stravaSyncing ? 'Syncing Strava…' : 'Sync Strava'}
              </button>
            ) : (
              <Link
                to="/settings"
                className="rounded-xl border border-[var(--aal-line)] bg-[var(--aal-card)] px-4 py-2.5 text-sm font-semibold text-[var(--aal-ink)]"
              >
                Connect Strava
              </Link>
            )}
            {overview?.connected ? (
              <button
                type="button"
                onClick={handleSyncCoros}
                disabled={anySyncing}
                className="inline-flex items-center gap-2 rounded-xl bg-sage px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-60"
              >
                <RefreshCw className={`h-4 w-4 ${corosSyncing ? 'sync-spin' : ''}`} />
                {corosSyncing ? 'Syncing COROS…' : 'Sync COROS'}
              </button>
            ) : (
              <Link
                to="/connect-coros"
                className="rounded-xl bg-sage px-4 py-2.5 text-sm font-semibold text-white"
              >
                Connect COROS
              </Link>
            )}
          </div>
        }
      />

      {error && <p className="mb-4 text-sm text-danger-muted">{error}</p>}

      <div className="mb-4">
        <TodaysCall compact />
      </div>

      {loading ? (
        <LoadingDots label="Loading dashboard…" />
      ) : (
        <>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <StatTile
              label="Recovery"
              value={fmt(fitness?.recovery_pct, 0, '%')}
              subtitle={fitness?.recovery_level || 'Open recovery'}
              to="/health/recovery"
              tone={fitness?.recovery_pct != null && fitness.recovery_pct < 40 ? 'warn' : 'good'}
            />
            <StatTile
              label="Sleep"
              value={fmt(health?.sleep_score, 0)}
              subtitle={health ? `${fmt(health.sleep_duration_min, 0)} min` : 'Open sleep'}
              to="/health/sleep"
            />
            <StatTile
              label="HRV"
              value={fmt(health?.hrv, 0, ' ms')}
              subtitle={health?.hrv_assessment || 'Open HRV'}
              to="/health/hrv"
            />
            <StatTile
              label="Resting HR"
              value={fmt(health?.resting_heart_rate, 0, ' bpm')}
              subtitle={`Stress ${fmt(health?.stress, 0)}`}
              to="/health/rhr"
            />
          </div>

          <div className="mt-6 grid gap-6 xl:grid-cols-2">
            <SectionCard title="COROS load ratio" subtitle="Official short/long load balance">
              <div className="h-56">
                {loadTrend.length ? (
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={loadTrend}>
                      <CartesianGrid stroke="var(--aal-line)" strokeDasharray="3 3" />
                      <XAxis dataKey="label" tick={{ fontSize: 12 }} />
                      <YAxis tick={{ fontSize: 12 }} />
                      <Tooltip />
                      <Line type="monotone" dataKey="ratio" stroke="#6b9ac4" strokeWidth={2.5} dot={false} />
                    </LineChart>
                  </ResponsiveContainer>
                ) : (
                  <p className="text-sm text-[var(--aal-muted)]">No COROS load history yet.</p>
                )}
              </div>
              <Link to="/training/load" className="mt-3 inline-block text-sm font-medium text-[var(--aal-link)]">
                View training load →
              </Link>
            </SectionCard>

            <SectionCard
              title="Weekly volume"
              subtitle={`ACWR ${stats?.acwr ?? '—'} · Acute ${fmt(stats?.acute_load_km, 1)} km`}
            >
              <div className="h-56">
                {volumeData.length ? (
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={volumeData}>
                      <CartesianGrid stroke="var(--aal-line)" strokeDasharray="3 3" />
                      <XAxis dataKey="label" tick={{ fontSize: 12 }} />
                      <YAxis tick={{ fontSize: 12 }} />
                      <Tooltip cursor={{ fill: 'transparent' }} />
                      <Bar
                        dataKey="km"
                        fill="#6b9080"
                        radius={[6, 6, 0, 0]}
                        activeBar={BarActiveGlow}
                      />
                    </BarChart>
                  </ResponsiveContainer>
                ) : (
                  <p className="text-sm text-[var(--aal-muted)]">No volume data yet.</p>
                )}
              </div>
              <Link to="/training/volume" className="mt-3 inline-block text-sm font-medium text-[var(--aal-link)]">
                View volume & ACWR →
              </Link>
            </SectionCard>
          </div>

          <div className="mt-6">
            <SectionCard
              title="Upcoming schedule"
              subtitle="Next planned COROS sessions"
              actions={
                <Link to="/training/schedule" className="text-sm font-medium text-[var(--aal-link)]">
                  Full schedule
                </Link>
              }
            >
              {(overview?.schedule || []).length === 0 ? (
                <p className="text-sm text-[var(--aal-muted)]">No schedule items synced.</p>
              ) : (
                <ul className="divide-y divide-[var(--aal-line)]">
                  {(overview?.schedule || []).slice(0, 3).map((item) => (
                    <li
                      key={`${item.external_id}-${item.schedule_date}`}
                      className="flex justify-between py-3 text-sm"
                    >
                      <div>
                        <p className="font-medium text-[var(--aal-ink)]">
                          {item.title || 'Planned session'}
                        </p>
                        <p className="text-[var(--aal-muted)]">
                          {item.schedule_date}
                          {item.sport_type ? ` · ${item.sport_type}` : ''}
                        </p>
                      </div>
                      <p className="text-[var(--aal-muted)]">
                        {item.duration_min != null ? `${Math.round(item.duration_min)} min` : '—'}
                      </p>
                    </li>
                  ))}
                </ul>
              )}
            </SectionCard>
          </div>

          <div className="mt-6">
            <SectionCard
              title="Recent activities"
              subtitle="Latest synced sessions"
              actions={
                <Link to="/activities" className="text-sm font-medium text-[var(--aal-link)]">
                  View all
                </Link>
              }
            >
              <ActivitiesTable
                athleteProfileId={profile?.id}
                embedded
                initialItems={recent}
                hideToolbar
              />
            </SectionCard>
          </div>
        </>
      )}

      <SyncResultModal
        open={Boolean(syncResult)}
        onClose={() => setSyncResult(null)}
        title={syncResult?.title}
        message={syncResult?.message}
        details={syncResult?.details}
      />
    </AppShell>
  )
}
