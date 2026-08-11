import { useEffect, useMemo, useState } from 'react'
import { Link, Navigate, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { ArrowLeft, ChevronLeft, ChevronRight } from 'lucide-react'
import {
  Area,
  AreaChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import {
  getActivity,
  getActivityPoints,
  listActivities,
  updateActivityNotes,
} from '../api/activities'
import { backfillCorosFitForActivity } from '../api/coros'
import { useAuth } from '../context/AuthContext'
import {
  formatClockTime,
  formatDateLong,
  formatDistanceKm,
  formatDuration,
} from '../utils/formatters'
import { getActivityTitle, formatSportType } from '../utils/sportTypes'
import { computeStreamStats, downsamplePoints } from '../utils/activityStreamStats'
import AppShell from './layout/AppShell'
import LoadingDots from './ui/LoadingDots'
import SportBadge from './SportBadge'

const TABS = [
  { id: 'timeline', label: 'Timeline' },
  { id: 'hr', label: 'HR' },
  { id: 'power', label: 'Power' },
  { id: 'data', label: 'Data' },
]

function Stat({ label, value, unit, hint }) {
  return (
    <div className="min-w-0">
      <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[var(--aal-muted)]">
        {label}
      </p>
      <p className="mt-0.5 truncate text-lg font-bold tabular-nums text-[var(--aal-ink)] sm:text-xl">
        {value}
        {unit ? (
          <span className="ml-1 text-xs font-medium text-[var(--aal-muted)]">{unit}</span>
        ) : null}
      </p>
      {hint ? <p className="text-[11px] text-[var(--aal-muted)]">{hint}</p> : null}
    </div>
  )
}

function formatElapsedTick(seconds) {
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${m}:${String(s).padStart(2, '0')}`
}

function StreamTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null
  return (
    <div className="rounded-xl border border-[var(--aal-line)] bg-[var(--aal-card)] px-3 py-2 text-xs shadow-lg">
      <p className="mb-1 font-medium text-[var(--aal-muted)]">t = {formatElapsedTick(label)}</p>
      {payload.map((entry) => (
        <p key={entry.dataKey} style={{ color: entry.color }} className="font-semibold">
          {entry.name}: {Number(entry.value).toFixed(entry.dataKey === 'power' ? 0 : 1)}{' '}
          {entry.unit || ''}
        </p>
      ))}
    </div>
  )
}

function StreamPanel({ title, unit, dataKey, color, data, area = false }) {
  const Chart = area ? AreaChart : LineChart
  return (
    <div className="rounded-xl border border-[var(--aal-line)] bg-[var(--aal-card)] p-3">
      <div className="mb-2 flex items-baseline justify-between">
        <p className="text-sm font-semibold text-[var(--aal-ink)]">{title}</p>
        <p className="text-xs text-[var(--aal-muted)]">Unit: {unit}</p>
      </div>
      <div className="h-36 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <Chart data={data}>
            <CartesianGrid stroke="var(--aal-line)" strokeDasharray="3 3" />
            <XAxis
              dataKey="elapsed_s"
              tickFormatter={formatElapsedTick}
              tick={{ fontSize: 10 }}
              stroke="var(--aal-muted)"
              minTickGap={28}
            />
            <YAxis
              tick={{ fontSize: 10 }}
              stroke="var(--aal-muted)"
              width={42}
              unit=""
              label={{
                value: unit,
                angle: -90,
                position: 'insideLeft',
                style: { fill: 'var(--aal-muted)', fontSize: 10 },
              }}
            />
            <Tooltip content={<StreamTooltip />} />
            {area ? (
              <Area
                type="monotone"
                dataKey={dataKey}
                name={title}
                unit={unit}
                stroke={color}
                fill={color}
                fillOpacity={0.25}
                strokeWidth={2}
                dot={false}
                isAnimationActive={false}
              />
            ) : (
              <Line
                type="monotone"
                dataKey={dataKey}
                name={title}
                unit={unit}
                stroke={color}
                strokeWidth={2}
                dot={false}
                isAnimationActive={false}
              />
            )}
          </Chart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}

export default function ActivityDetailPage() {
  const { activityId } = useParams()
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const { isAuthenticated, profile } = useAuth()
  const [activity, setActivity] = useState(null)
  const [pointsPayload, setPointsPayload] = useState(null)
  const [siblings, setSiblings] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [tab, setTab] = useState(searchParams.get('tab') || 'timeline')
  const [notes, setNotes] = useState('')
  const [savingNotes, setSavingNotes] = useState(false)
  const [notesMessage, setNotesMessage] = useState('')
  const [streamMessage, setStreamMessage] = useState('')
  const [fetchingStreams, setFetchingStreams] = useState(false)

  useEffect(() => {
    let cancelled = false
    async function load() {
      setLoading(true)
      setError('')
      setStreamMessage('')
      try {
        const [activityData, pointsData] = await Promise.all([
          getActivity(activityId),
          getActivityPoints(activityId),
        ])
        if (cancelled) return
        setActivity(activityData)
        setPointsPayload(pointsData)
        setNotes(activityData.notes || '')

        // If timeline is empty, try COROS FIT (direct COROS activity or Strava twin).
        const needsStreams = !pointsData?.has_points
        const canTryCoros =
          activityData?.provider === 'coros' || activityData?.provider === 'strava'
        if (needsStreams && canTryCoros) {
          setFetchingStreams(true)
          setStreamMessage('Fetching COROS timeline streams…')
          try {
            const fitResult = await backfillCorosFitForActivity(activityId)
            if (cancelled) return
            if (fitResult?.ok && !fitResult?.skipped) {
              const refreshed = await getActivityPoints(activityId)
              if (!cancelled) {
                setPointsPayload(refreshed)
                setStreamMessage(
                  refreshed?.has_points
                    ? 'COROS streams loaded.'
                    : 'FIT downloaded but no usable stream points were found.',
                )
              }
            } else if (fitResult?.reason === 'quota_exhausted') {
              setStreamMessage('COROS FIT daily quota reached. Try again tomorrow.')
            } else if (fitResult?.reason === 'no_coros_source') {
              setStreamMessage('')
            } else if (fitResult?.reason === 'no_fit_url') {
              setStreamMessage('COROS did not return a FIT download URL for this activity.')
            } else if (fitResult?.skipped) {
              setStreamMessage('')
            } else if (fitResult?.reason) {
              setStreamMessage(`Could not load COROS streams (${fitResult.reason}).`)
            }
          } catch (fitErr) {
            if (!cancelled) {
              setStreamMessage(fitErr.message || 'Failed to fetch COROS streams.')
            }
          } finally {
            if (!cancelled) setFetchingStreams(false)
          }
        }

        if (profile?.id) {
          const page = await listActivities(profile.id, {
            page: 1,
            page_size: 200,
            sort: 'date_desc',
          })
          if (!cancelled) setSiblings(page.items || [])
        }
      } catch (err) {
        if (!cancelled) setError(err.message || 'Failed to load activity.')
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    load()
    return () => {
      cancelled = true
    }
  }, [activityId, profile?.id])

  const chartData = useMemo(() => {
    const points = downsamplePoints(pointsPayload?.points || [], 900)
    return points.map((point) => ({
      ...point,
      speed_kmh: point.speed_mps != null ? point.speed_mps * 3.6 : null,
    }))
  }, [pointsPayload])

  const streamStats = useMemo(
    () => computeStreamStats(pointsPayload?.points || []),
    [pointsPayload],
  )

  const metrics = pointsPayload?.metrics || []
  const siblingIndex = siblings.findIndex((row) => String(row.id) === String(activityId))

  async function saveNotes() {
    setSavingNotes(true)
    setNotesMessage('')
    try {
      const updated = await updateActivityNotes(activityId, notes)
      setActivity(updated)
      setNotesMessage('Notes saved.')
    } catch (err) {
      setNotesMessage(err.message || 'Failed to save notes.')
    } finally {
      setSavingNotes(false)
    }
  }

  if (!isAuthenticated) return <Navigate to="/signin" replace />

  if (loading) {
    return (
      <AppShell title="Activity">
        <LoadingDots label="Loading activity detail…" />
      </AppShell>
    )
  }

  if (error || !activity) {
    return (
      <AppShell title="Activity">
        <p className="text-danger-muted">{error || 'Activity not found.'}</p>
      </AppShell>
    )
  }

  const isRide =
    formatSportType(activity.sport_type) === 'Bike' ||
    (activity.sport_type || '').toLowerCase().includes('ride')
  const avgSpeed =
    activity.distance_m > 0 && activity.moving_time_s > 0
      ? (activity.distance_m / activity.moving_time_s) * 3.6
      : streamStats.avgSpeedKmh
  const avgPace =
    !isRide && activity.distance_m > 0 && activity.moving_time_s > 0
      ? activity.moving_time_s / 60 / (activity.distance_m / 1000)
      : null
  const avgHr = activity.average_heartrate ?? streamStats.avgHr
  const maxHr = activity.max_heartrate ?? streamStats.maxHr

  return (
    <AppShell title="Activity">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <Link
          to="/activities"
          className="inline-flex items-center gap-2 text-sm text-[var(--aal-muted)] hover:text-sage"
        >
          <ArrowLeft className="h-4 w-4" /> All activities
        </Link>
        <div className="flex items-center gap-2">
          <button
            type="button"
            disabled={siblingIndex < 0 || siblingIndex >= siblings.length - 1}
            onClick={() => navigate(`/activities/${siblings[siblingIndex + 1].id}`)}
            className="rounded-lg border border-[var(--aal-line)] p-2 disabled:opacity-40"
            title="Older activity"
          >
            <ChevronLeft className="h-4 w-4" />
          </button>
          <button
            type="button"
            disabled={siblingIndex <= 0}
            onClick={() => navigate(`/activities/${siblings[siblingIndex - 1].id}`)}
            className="rounded-lg border border-[var(--aal-line)] p-2 disabled:opacity-40"
            title="Newer activity"
          >
            <ChevronRight className="h-4 w-4" />
          </button>
        </div>
      </div>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_280px]">
        <div className="space-y-4">
          <section className="rounded-2xl border border-[var(--aal-line)] bg-[var(--aal-card)] p-5">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <SportBadge sportType={activity.sport_type} />
                <h1 className="mt-2 text-2xl font-bold sm:text-3xl">{getActivityTitle(activity)}</h1>
                <p className="mt-1 text-sm text-[var(--aal-muted)]">
                  {formatDateLong(activity.activity_date)} · {formatClockTime(activity.activity_date)}
                  {activity.provider ? ` · ${String(activity.provider).toUpperCase()}` : ''}
                </p>
              </div>
              <div className="text-right">
                <p className="text-3xl font-bold tabular-nums sm:text-4xl">
                  {(activity.distance_m / 1000).toFixed(2)}
                  <span className="ml-1 text-base font-medium text-[var(--aal-muted)]">km</span>
                </p>
                <p className="mt-1 text-xl font-semibold tabular-nums text-[var(--aal-muted)]">
                  {formatDuration(activity.moving_time_s)}
                  <span className="ml-1 text-xs font-medium">moving</span>
                </p>
              </div>
            </div>

            <div className="mt-5 grid gap-4 border-t border-[var(--aal-line)] pt-4 sm:grid-cols-2 lg:grid-cols-4">
              <Stat
                label={isRide ? 'Avg speed' : 'Avg pace'}
                value={
                  isRide
                    ? avgSpeed != null
                      ? avgSpeed.toFixed(1)
                      : '—'
                    : avgPace != null
                      ? avgPace.toFixed(2)
                      : '—'
                }
                unit={isRide ? 'km/h' : 'min/km'}
              />
              <Stat
                label="Avg HR"
                value={avgHr != null ? Math.round(avgHr) : '—'}
                unit="bpm"
                hint={maxHr != null ? `Max ${Math.round(maxHr)} bpm` : undefined}
              />
              <Stat
                label="Avg power"
                value={streamStats.avgPower != null ? Math.round(streamStats.avgPower) : '—'}
                unit="W"
                hint={
                  streamStats.maxPower != null ? `Max ${Math.round(streamStats.maxPower)} W` : undefined
                }
              />
              <Stat
                label="Cadence"
                value={streamStats.avgCadence != null ? Math.round(streamStats.avgCadence) : '—'}
                unit="rpm"
              />
              <Stat
                label="Elev gain"
                value={streamStats.hasElevation ? Math.round(streamStats.elevGainM) : '—'}
                unit="m"
              />
              <Stat label="Sport" value={formatSportType(activity.sport_type) || '—'} />
              <Stat label="Provider" value={(activity.provider || '—').toUpperCase()} />
              <Stat
                label="Track points"
                value={pointsPayload?.has_points ? String(pointsPayload.points.length) : '0'}
              />
            </div>
          </section>

          <div className="flex flex-wrap gap-1 rounded-xl border border-[var(--aal-line)] bg-[var(--aal-card)] p-1">
            {TABS.map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => setTab(item.id)}
                className={`rounded-lg px-4 py-2 text-sm font-medium ${
                  tab === item.id
                    ? 'bg-sage/15 text-sage'
                    : 'text-[var(--aal-muted)] hover:text-[var(--aal-ink)]'
                }`}
              >
                {item.label}
              </button>
            ))}
          </div>

          {tab === 'timeline' && (
            <div className="space-y-3">
              {metrics.includes('power') && (
                <StreamPanel
                  title="Power"
                  unit="W"
                  dataKey="power"
                  color="#8b5cf6"
                  data={chartData}
                  area
                />
              )}
              {metrics.includes('heart_rate') && (
                <StreamPanel
                  title="Heart rate"
                  unit="bpm"
                  dataKey="heart_rate"
                  color="#ef4444"
                  data={chartData}
                />
              )}
              {metrics.includes('cadence') && (
                <StreamPanel
                  title="Cadence"
                  unit="rpm"
                  dataKey="cadence"
                  color="#d946ef"
                  data={chartData}
                />
              )}
              {metrics.includes('speed_mps') && (
                <StreamPanel
                  title="Speed"
                  unit="km/h"
                  dataKey="speed_kmh"
                  color="#10b981"
                  data={chartData}
                />
              )}
              {metrics.includes('altitude_m') && (
                <StreamPanel
                  title="Elevation"
                  unit="m"
                  dataKey="altitude_m"
                  color="#f59e0b"
                  data={chartData}
                  area
                />
              )}
              {!metrics.length && (
                <div className="rounded-xl border border-dashed border-[var(--aal-line)] p-6 text-sm text-[var(--aal-muted)]">
                  {fetchingStreams ? (
                    <LoadingDots label="Fetching COROS timeline streams…" />
                  ) : (
                    <p>No stream data available for this activity yet.</p>
                  )}
                  {streamMessage ? <p className="mt-2 text-xs">{streamMessage}</p> : null}
                </div>
              )}
              {metrics.length && streamMessage ? (
                <p className="text-xs text-[var(--aal-muted)]">{streamMessage}</p>
              ) : null}
            </div>
          )}

          {tab === 'hr' && (
            <div className="space-y-3">
              {metrics.includes('heart_rate') ? (
                <StreamPanel
                  title="Heart rate"
                  unit="bpm"
                  dataKey="heart_rate"
                  color="#ef4444"
                  data={chartData}
                />
              ) : (
                <p className="text-sm text-[var(--aal-muted)]">No heart-rate stream for this activity.</p>
              )}
            </div>
          )}

          {tab === 'power' && (
            <div className="space-y-3">
              {metrics.includes('power') ? (
                <StreamPanel
                  title="Power"
                  unit="W"
                  dataKey="power"
                  color="#8b5cf6"
                  data={chartData}
                  area
                />
              ) : (
                <p className="text-sm text-[var(--aal-muted)]">No power stream for this activity.</p>
              )}
            </div>
          )}

          {tab === 'data' && (
            <section className="rounded-2xl border border-[var(--aal-line)] bg-[var(--aal-card)] p-5">
              <h2 className="mb-4 text-lg font-semibold">All activity data</h2>
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {[
                  ['Activity ID', activity.id],
                  ['Provider', activity.provider],
                  ['External ID', activity.external_activity_id],
                  ['Strava ID', activity.strava_activity_id],
                  ['Sport type', activity.sport_type],
                  ['Source FIT', activity.source_fit_file],
                  ['Distance', formatDistanceKm(activity.distance_m)],
                  ['Moving time', formatDuration(activity.moving_time_s)],
                  ['Avg HR', avgHr != null ? `${Math.round(avgHr)} bpm` : '—'],
                  ['Max HR', maxHr != null ? `${Math.round(maxHr)} bpm` : '—'],
                  [
                    'Avg power',
                    streamStats.avgPower != null ? `${Math.round(streamStats.avgPower)} W` : '—',
                  ],
                  [
                    'Avg cadence',
                    streamStats.avgCadence != null ? `${Math.round(streamStats.avgCadence)} rpm` : '—',
                  ],
                  [
                    'Elev gain',
                    streamStats.hasElevation ? `${Math.round(streamStats.elevGainM)} m` : '—',
                  ],
                  ['Stream metrics', metrics.join(', ') || 'None'],
                ].map(([label, value]) => (
                  <div key={label}>
                    <p className="text-[10px] font-semibold uppercase tracking-wide text-[var(--aal-muted)]">
                      {label}
                    </p>
                    <p className="mt-1 break-all text-sm">{value ?? '—'}</p>
                  </div>
                ))}
              </div>
            </section>
          )}
        </div>

        <aside className="rounded-2xl border border-[var(--aal-line)] bg-[var(--aal-card)] p-4 xl:sticky xl:top-4 xl:self-start">
          <h2 className="text-lg font-semibold">Notes</h2>
          <p className="mt-1 text-xs text-[var(--aal-muted)]">
            Saved to your account for this activity.
          </p>
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            rows={10}
            placeholder="Type a note about this workout…"
            className="mt-3 w-full rounded-xl border border-[var(--aal-line)] bg-[var(--aal-bg)] px-3 py-2 text-sm outline-none focus:border-sage"
          />
          <button
            type="button"
            onClick={saveNotes}
            disabled={savingNotes}
            className="mt-3 w-full rounded-xl bg-sage px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-60"
          >
            {savingNotes ? 'Saving…' : 'Save notes'}
          </button>
          {notesMessage && (
            <p className="mt-2 text-xs text-[var(--aal-muted)]">{notesMessage}</p>
          )}
        </aside>
      </div>
    </AppShell>
  )
}
