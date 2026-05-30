import { formatDurationHours, formatDistanceKm } from './formatters'
import { formatSportType } from './sportTypes'

export function computeActivityOverview(activities) {
  if (!activities?.length) {
    return {
      totalActivities: 0,
      totalDistanceKm: 0,
      totalMovingHours: 0,
      avgHeartRate: null,
      activitiesThisWeek: 0,
      topSport: '—',
      topSportCount: 0,
      longestDistanceKm: 0,
      sportBreakdown: [],
      maxHeartRate: null,
    }
  }

  const now = Date.now()
  const weekAgo = now - 7 * 24 * 60 * 60 * 1000

  let totalDistanceM = 0
  let totalMovingS = 0
  let hrSum = 0
  let hrCount = 0
  let maxHr = null
  let longestDistanceM = 0
  let activitiesThisWeek = 0
  const sportCounts = {}

  for (const activity of activities) {
    totalDistanceM += activity.distance_m || 0
    totalMovingS += activity.moving_time_s || 0

    if (activity.average_heartrate) {
      hrSum += activity.average_heartrate
      hrCount += 1
    }
    if (activity.max_heartrate && (maxHr == null || activity.max_heartrate > maxHr)) {
      maxHr = activity.max_heartrate
    }
    if (activity.distance_m > longestDistanceM) {
      longestDistanceM = activity.distance_m
    }
    if (new Date(activity.activity_date).getTime() >= weekAgo) {
      activitiesThisWeek += 1
    }

    const sport = formatSportType(activity.sport_type)
    sportCounts[sport] = (sportCounts[sport] || 0) + 1
  }

  const sportBreakdown = Object.entries(sportCounts)
    .map(([sport, count]) => ({ sport, count }))
    .sort((a, b) => b.count - a.count)

  const top = sportBreakdown[0]

  return {
    totalActivities: activities.length,
    totalDistanceKm: (totalDistanceM / 1000).toFixed(1),
    totalMovingHours: formatDurationHours(totalMovingS),
    avgHeartRate: hrCount ? Math.round(hrSum / hrCount) : null,
    activitiesThisWeek,
    topSport: top?.sport || '—',
    topSportCount: top?.count || 0,
    longestDistanceKm: (longestDistanceM / 1000).toFixed(1),
    sportBreakdown,
    maxHeartRate: maxHr ? Math.round(maxHr) : null,
  }
}

export function formatOverviewValue(value, suffix = '') {
  if (value == null || value === '—') return '—'
  return `${value}${suffix}`
}
