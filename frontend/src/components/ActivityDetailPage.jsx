import { useEffect, useState } from 'react'
import { Link, Navigate, useParams } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'
import { getActivity, getActivityPoints } from '../api/activities'
import { useAuth } from '../context/AuthContext'
import {
  formatDate,
  formatDistanceKm,
  formatDuration,
} from '../utils/formatters'
import { getActivitySubtitle, getActivityTitle, formatSportType } from '../utils/sportTypes'
import { pagePaddingClass, pageShellClass } from '../utils/statusColors'
import ActivityCharts from './ActivityCharts'
import Navigation from './Navigation'
import Card from './ui/Card'
import MetricCard from './ui/MetricCard'
import SportBadge from './SportBadge'

function DetailField({ label, value }) {
  return (
    <div>
      <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</p>
      <p className="mt-1 text-sm text-slate-900 dark:text-white">{value || '—'}</p>
    </div>
  )
}

export default function ActivityDetailPage() {
  const { activityId } = useParams()
  const { isAuthenticated } = useAuth()
  const [activity, setActivity] = useState(null)
  const [pointsPayload, setPointsPayload] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    async function load() {
      setLoading(true)
      setError('')
      try {
        const [activityData, pointsData] = await Promise.all([
          getActivity(activityId),
          getActivityPoints(activityId),
        ])
        setActivity(activityData)
        setPointsPayload(pointsData)
      } catch (err) {
        setError(err.message || 'Failed to load activity.')
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [activityId])

  if (!isAuthenticated) return <Navigate to="/signin" replace />

  if (loading) {
    return (
      <div className={pageShellClass}>
        <Navigation subtitle="Activity Detail" />
        <main className={pagePaddingClass}>Loading activity...</main>
      </div>
    )
  }

  if (error || !activity) {
    return (
      <div className={pageShellClass}>
        <Navigation subtitle="Activity Detail" />
        <main className={pagePaddingClass}>
          <Card className="p-6 text-danger-muted">{error || 'Activity not found.'}</Card>
        </main>
      </div>
    )
  }

  const subtitle = getActivitySubtitle(activity)
  const isRide =
    formatSportType(activity.sport_type) === 'Bike' ||
    (activity.sport_type || '').toLowerCase().includes('ride')
  const avgPace =
    !isRide && activity.distance_m > 0 && activity.moving_time_s > 0
      ? `${(activity.moving_time_s / 60 / (activity.distance_m / 1000)).toFixed(2)} min/km`
      : '—'
  const avgSpeed =
    activity.distance_m > 0 && activity.moving_time_s > 0
      ? `${((activity.distance_m / activity.moving_time_s) * 3.6).toFixed(1)} km/h`
      : '—'

  return (
    <div className={pageShellClass}>
      <Navigation subtitle="Activity Detail" />

      <main className={`${pagePaddingClass} space-y-6`}>
        <Link
          to="/dashboard"
          className="inline-flex items-center gap-2 text-sm text-slate-500 hover:text-sage"
        >
          <ArrowLeft className="h-4 w-4" /> Back to dashboard
        </Link>

        <Card className="p-6">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <SportBadge sportType={activity.sport_type} />
              <h1 className="mt-3 text-3xl font-bold text-slate-900 dark:text-white">
                {getActivityTitle(activity)}
              </h1>
              {subtitle && <p className="mt-1 text-slate-500">{subtitle}</p>}
              <p className="mt-2 text-sm text-slate-500">{formatDate(activity.activity_date)}</p>
            </div>
          </div>

          <div className="mt-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <MetricCard label="Distance" value={formatDistanceKm(activity.distance_m)} />
            <MetricCard label="Moving Time" value={formatDuration(activity.moving_time_s)} />
            <MetricCard
              label="Avg Heart Rate"
              value={activity.average_heartrate ? `${Math.round(activity.average_heartrate)} bpm` : '—'}
            />
            <MetricCard
              label="Max Heart Rate"
              value={activity.max_heartrate ? `${Math.round(activity.max_heartrate)} bpm` : '—'}
            />
            {!isRide && (
              <MetricCard label="Avg Pace" value={avgPace} />
            )}
            <MetricCard label="Avg Speed" value={avgSpeed} />
          </div>
        </Card>

        <ActivityCharts
          points={pointsPayload?.points || []}
          availableMetrics={pointsPayload?.metrics || []}
          sportType={activity.sport_type}
        />

        <Card className="p-6">
          <h2 className="text-lg font-semibold text-slate-900 dark:text-white">All activity data</h2>
          <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <DetailField label="Activity ID" value={activity.id} />
            <DetailField label="Strava Activity ID" value={activity.strava_activity_id} />
            <DetailField label="Sport Type" value={activity.sport_type} />
            <DetailField label="Source FIT File" value={activity.source_fit_file} />
            <DetailField label="Track Points" value={pointsPayload?.has_points ? pointsPayload.points.length : 'None'} />
            <DetailField
              label="Imported At"
              value={activity.created_at ? formatDate(activity.created_at) : '—'}
            />
          </div>
        </Card>
      </main>
    </div>
  )
}
