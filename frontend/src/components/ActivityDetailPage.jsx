import { useEffect, useMemo, useState } from 'react'
import { Navigate, useNavigate, useParams } from 'react-router-dom'
import {
  enrichActivityDetail,
  getActivity,
  getActivityPoints,
  listActivities,
} from '../api/activities'
import { backfillCorosFitForActivity } from '../api/coros'
import { useAuth } from '../context/AuthContext'
import {
  formatDistanceKm,
  formatDuration,
} from '../utils/formatters'
import { formatSportType, getSportFamily } from '../utils/sportTypes'
import { computeStreamStats, downsamplePoints } from '../utils/activityStreamStats'
import AppShell from './layout/AppShell'
import LoadingDots from './ui/LoadingDots'
import ActivityDetailChrome from './activity/ActivityDetailChrome'
import ActivityNotesPanel from './activity/ActivityNotesPanel'
import EnduranceDetailBody from './activity/EnduranceDetailBody'
import GenericDetailBody from './activity/GenericDetailBody'
import StrengthDetailBody from './activity/StrengthDetailBody'
import SwimDetailBody from './activity/SwimDetailBody'
import { formatPace } from './activity/detailFormatters'

function buildHero(activity, family, streamStats, detail) {
  const summary = detail?.summary || {}
  const avgHr = activity.average_heartrate ?? summary.avg_hr ?? streamStats.avgHr
  const maxHr = activity.max_heartrate ?? summary.max_hr ?? streamStats.maxHr
  const calories = summary.calories
  const elev =
    summary.elev_gain_m != null
      ? summary.elev_gain_m
      : streamStats.hasElevation
        ? streamStats.elevGainM
        : null

  const avgSpeed =
    summary.avg_speed != null
      ? summary.avg_speed
      : activity.distance_m > 0 && activity.moving_time_s > 0
        ? (activity.distance_m / activity.moving_time_s) * 3.6
        : streamStats.avgSpeedKmh

  const avgPace =
    summary.avg_pace != null
      ? summary.avg_pace
      : activity.distance_m > 0 && activity.moving_time_s > 0
        ? activity.moving_time_s / 60 / (activity.distance_m / 1000)
        : null

  if (family === 'strength' || family === 'yoga') {
    return {
      heroPrimary: (
        <p className="text-3xl font-bold tabular-nums sm:text-4xl">
          {formatDuration(activity.moving_time_s)}
        </p>
      ),
      heroStats: [
        {
          label: 'Avg HR',
          value: avgHr != null ? Math.round(avgHr) : '—',
          unit: 'bpm',
          hint: maxHr != null ? `Max ${Math.round(maxHr)} bpm` : undefined,
        },
        {
          label: 'Calories',
          value: calories != null ? Math.round(calories) : '—',
          unit: calories != null ? 'kcal' : undefined,
        },
        { label: 'Sport', value: formatSportType(activity.sport_type) || '—' },
        { label: 'Provider', value: (activity.provider || '—').toUpperCase() },
      ],
    }
  }

  if (family === 'swim') {
    return {
      heroPrimary: (
        <p className="text-3xl font-bold tabular-nums sm:text-4xl">
          {(activity.distance_m / 1000).toFixed(2)}
          <span className="ml-1 text-base font-medium text-[var(--aal-muted)]">km</span>
        </p>
      ),
      heroStats: [
        {
          label: 'Avg HR',
          value: avgHr != null ? Math.round(avgHr) : '—',
          unit: 'bpm',
          hint: maxHr != null ? `Max ${Math.round(maxHr)} bpm` : undefined,
        },
        {
          label: 'Strokes',
          value: summary.stroke_count != null ? summary.stroke_count : '—',
        },
        {
          label: 'SWOLF',
          value: summary.swolf != null ? Math.round(summary.swolf) : '—',
        },
        {
          label: 'Pool',
          value: summary.pool_length_m != null ? summary.pool_length_m : '—',
          unit: summary.pool_length_m != null ? 'm' : undefined,
        },
      ],
    }
  }

  if (family === 'ride') {
    return {
      heroPrimary: (
        <p className="text-3xl font-bold tabular-nums sm:text-4xl">
          {(activity.distance_m / 1000).toFixed(2)}
          <span className="ml-1 text-base font-medium text-[var(--aal-muted)]">km</span>
        </p>
      ),
      heroStats: [
        {
          label: 'Avg speed',
          value: avgSpeed != null ? Number(avgSpeed).toFixed(1) : '—',
          unit: 'km/h',
        },
        {
          label: 'Avg power',
          value:
            summary.avg_power != null
              ? Math.round(summary.avg_power)
              : streamStats.avgPower != null
                ? Math.round(streamStats.avgPower)
                : '—',
          unit: 'W',
          hint:
            summary.max_power != null || streamStats.maxPower != null
              ? `Max ${Math.round(summary.max_power ?? streamStats.maxPower)} W`
              : undefined,
        },
        {
          label: 'Avg HR',
          value: avgHr != null ? Math.round(avgHr) : '—',
          unit: 'bpm',
          hint: maxHr != null ? `Max ${Math.round(maxHr)} bpm` : undefined,
        },
        {
          label: 'Elev gain',
          value: elev != null ? Math.round(elev) : '—',
          unit: 'm',
        },
      ],
    }
  }

  if (family === 'run') {
    return {
      heroPrimary: (
        <p className="text-3xl font-bold tabular-nums sm:text-4xl">
          {(activity.distance_m / 1000).toFixed(2)}
          <span className="ml-1 text-base font-medium text-[var(--aal-muted)]">km</span>
        </p>
      ),
      heroStats: [
        {
          label: 'Avg pace',
          value: avgPace != null ? formatPace(avgPace) : '—',
          unit: 'min/km',
        },
        {
          label: 'Avg HR',
          value: avgHr != null ? Math.round(avgHr) : '—',
          unit: 'bpm',
          hint: maxHr != null ? `Max ${Math.round(maxHr)} bpm` : undefined,
        },
        {
          label: 'Cadence',
          value:
            summary.avg_cadence != null
              ? Math.round(summary.avg_cadence)
              : streamStats.avgCadence != null
                ? Math.round(streamStats.avgCadence)
                : '—',
          unit: 'spm',
        },
        {
          label: 'Elev gain',
          value: elev != null ? Math.round(elev) : '—',
          unit: 'm',
        },
      ],
    }
  }

  // walk / row / other
  return {
    heroPrimary: (
      <p className="text-3xl font-bold tabular-nums sm:text-4xl">
        {activity.distance_m > 0 ? (
          <>
            {(activity.distance_m / 1000).toFixed(2)}
            <span className="ml-1 text-base font-medium text-[var(--aal-muted)]">km</span>
          </>
        ) : (
          formatDuration(activity.moving_time_s)
        )}
      </p>
    ),
    heroStats: [
      {
        label: 'Avg HR',
        value: avgHr != null ? Math.round(avgHr) : '—',
        unit: 'bpm',
        hint: maxHr != null ? `Max ${Math.round(maxHr)} bpm` : undefined,
      },
      {
        label: 'Calories',
        value: calories != null ? Math.round(calories) : '—',
      },
      { label: 'Sport', value: formatSportType(activity.sport_type) || '—' },
      { label: 'Provider', value: (activity.provider || '—').toUpperCase() },
    ],
  }
}

export default function ActivityDetailPage() {
  const { activityId } = useParams()
  const navigate = useNavigate()
  const { isAuthenticated, profile } = useAuth()
  const [activity, setActivity] = useState(null)
  const [pointsPayload, setPointsPayload] = useState(null)
  const [siblings, setSiblings] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [streamMessage, setStreamMessage] = useState('')
  const [fetchingStreams, setFetchingStreams] = useState(false)
  const [enrichMessage, setEnrichMessage] = useState('')

  useEffect(() => {
    let cancelled = false
    async function load() {
      setLoading(true)
      setError('')
      setStreamMessage('')
      setEnrichMessage('')
      try {
        const [activityData, pointsData] = await Promise.all([
          getActivity(activityId),
          getActivityPoints(activityId),
        ])
        if (cancelled) return
        setActivity(activityData)
        setPointsPayload(pointsData)

        // Enrich sport-specific detail (laps / exercises) when missing or stale path.
        if (!activityData.detail) {
          setEnrichMessage('Loading workout detail…')
          try {
            const enrichResult = await enrichActivityDetail(activityId)
            if (cancelled) return
            if (enrichResult?.activity) {
              setActivity(enrichResult.activity)
            } else if (enrichResult?.detail) {
              setActivity((prev) => (prev ? { ...prev, detail: enrichResult.detail } : prev))
            }
            if (enrichResult?.ok) {
              setEnrichMessage(
                enrichResult.skipped
                  ? ''
                  : enrichResult.sources?.length
                    ? `Detail from ${enrichResult.sources.map((s) => s.toUpperCase()).join(' + ')}`
                    : '',
              )
            } else if (enrichResult?.reason === 'no_detail_sources') {
              setEnrichMessage('')
            } else if (enrichResult?.reason) {
              setEnrichMessage(`Detail enrich: ${enrichResult.reason}`)
            }
          } catch (enrichErr) {
            if (!cancelled) {
              setEnrichMessage(enrichErr.message || 'Could not enrich activity detail.')
            }
          }
        }

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

  const streamPoints = useMemo(
    () => downsamplePoints(pointsPayload?.points || [], 4000),
    [pointsPayload],
  )

  const streamStats = useMemo(
    () => computeStreamStats(pointsPayload?.points || []),
    [pointsPayload],
  )

  const metrics = pointsPayload?.metrics || []
  const siblingIndex = siblings.findIndex((row) => String(row.id) === String(activityId))
  const family = activity?.sport_family || getSportFamily(activity?.sport_type)
  const detail = activity?.detail || null

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

  const { heroPrimary, heroStats } = buildHero(activity, family, streamStats, detail)
  const avgHr = activity.average_heartrate ?? detail?.summary?.avg_hr ?? streamStats.avgHr
  const maxHr = activity.max_heartrate ?? detail?.summary?.max_hr ?? streamStats.maxHr

  const dataRows = [
    ['Activity ID', activity.id],
    ['Provider', activity.provider],
    ['External ID', activity.external_activity_id],
    ['Strava ID', activity.strava_activity_id],
    ['Sport type', activity.sport_type],
    ['Sport family', family],
    ['Source FIT', activity.source_fit_file],
    ['Distance', formatDistanceKm(activity.distance_m)],
    ['Moving time', formatDuration(activity.moving_time_s)],
    ['Avg HR', avgHr != null ? `${Math.round(avgHr)} bpm` : '—'],
    ['Max HR', maxHr != null ? `${Math.round(maxHr)} bpm` : '—'],
    [
      'Avg power',
      streamStats.avgPower != null
        ? `${Math.round(streamStats.avgPower)} W`
        : detail?.summary?.avg_power != null
          ? `${Math.round(detail.summary.avg_power)} W`
          : '—',
    ],
    [
      'Avg cadence',
      streamStats.avgCadence != null
        ? `${Math.round(streamStats.avgCadence)}`
        : detail?.summary?.avg_cadence != null
          ? `${Math.round(detail.summary.avg_cadence)}`
          : '—',
    ],
    [
      'Elev gain',
      streamStats.hasElevation
        ? `${Math.round(streamStats.elevGainM)} m`
        : detail?.summary?.elev_gain_m != null
          ? `${Math.round(detail.summary.elev_gain_m)} m`
          : '—',
    ],
    ['Calories', detail?.summary?.calories != null ? Math.round(detail.summary.calories) : '—'],
    ['Laps', detail?.laps?.length ?? 0],
    ['Exercises', detail?.exercises?.length ?? 0],
    ['Detail sources', (detail?.sources || []).join(', ') || 'None'],
    ['Stream metrics', metrics.join(', ') || 'None'],
  ]

  async function handlePullDetail() {
    const fitResult = await backfillCorosFitForActivity(activityId)
    // Re-fetch the activity so updated detail_json (exercises) is reflected.
    try {
      const refreshed = await getActivity(activityId)
      setActivity(refreshed)
    } catch (_) {
      // ignore refresh errors; the pull result is still returned
    }
    return fitResult
  }

  const bodyProps = {
    detail,
    metrics,
    chartData,
    streamPoints,
    fetchingStreams,
    streamMessage,
    dataRows,
    notesPanel: <ActivityNotesPanel activityId={activityId} />,
    onPullDetail: handlePullDetail,
  }

  const body =
    family === 'strength' || family === 'yoga' ? (
      <StrengthDetailBody {...bodyProps} />
    ) : family === 'run' || family === 'ride' ? (
      <EnduranceDetailBody family={family} {...bodyProps} />
    ) : family === 'swim' ? (
      <SwimDetailBody {...bodyProps} />
    ) : (
      <GenericDetailBody
        {...bodyProps}
        familyLabel={formatSportType(activity.sport_type)}
      />
    )

  return (
    <AppShell title="Activity">
      <ActivityDetailChrome
        activity={activity}
        siblings={siblings}
        siblingIndex={siblingIndex}
        onOlder={() => navigate(`/activities/${siblings[siblingIndex + 1].id}`)}
        onNewer={() => navigate(`/activities/${siblings[siblingIndex - 1].id}`)}
        heroStats={heroStats}
        heroPrimary={heroPrimary}
        enrichMessage={enrichMessage}
      >
        {body}
      </ActivityDetailChrome>
    </AppShell>
  )
}
