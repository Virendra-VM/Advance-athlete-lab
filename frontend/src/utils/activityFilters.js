import { formatSportType } from './sportTypes'

export const OVERVIEW_PERIODS = [
  { value: 'all', label: 'All time' },
  { value: 'week', label: 'This week' },
  { value: 'month', label: 'This month' },
  { value: '90d', label: 'Last 90 days' },
  { value: 'year', label: 'This year' },
]

export const HISTORY_SORT_OPTIONS = [
  { value: 'date_desc', label: 'Newest first' },
  { value: 'date_asc', label: 'Oldest first' },
  { value: 'distance_desc', label: 'Longest first' },
  { value: 'distance_asc', label: 'Shortest first' },
]

function startOfWeek(date) {
  const copy = new Date(date)
  const day = copy.getDay()
  const diff = day === 0 ? -6 : 1 - day
  copy.setDate(copy.getDate() + diff)
  copy.setHours(0, 0, 0, 0)
  return copy
}

export function getPeriodStart(period) {
  const now = new Date()
  if (period === 'week') return startOfWeek(now)
  if (period === 'month') return new Date(now.getFullYear(), now.getMonth(), 1)
  if (period === '90d') return new Date(now.getTime() - 90 * 24 * 60 * 60 * 1000)
  if (period === 'year') return new Date(now.getFullYear(), 0, 1)
  return null
}

export function collectSportOptions(activities) {
  const sports = new Set()
  for (const activity of activities) {
    sports.add(formatSportType(activity.sport_type))
  }
  return ['All sports', ...Array.from(sports).sort()]
}

export function filterOverviewActivities(activities, { period, sport }) {
  let rows = [...activities]
  const periodStart = getPeriodStart(period)
  if (periodStart) {
    rows = rows.filter((activity) => new Date(activity.activity_date) >= periodStart)
  }
  if (sport && sport !== 'All sports') {
    rows = rows.filter((activity) => formatSportType(activity.sport_type) === sport)
  }
  return rows
}

export function filterHistoryActivities(
  activities,
  { search, sport, dateFrom, dateTo, minDistanceKm, hasHr, sort },
) {
  let rows = [...activities]

  if (search?.trim()) {
    const query = search.trim().toLowerCase()
    rows = rows.filter((activity) => {
      const title = (activity.name || '').toLowerCase()
      const sportLabel = formatSportType(activity.sport_type).toLowerCase()
      return title.includes(query) || sportLabel.includes(query)
    })
  }

  if (sport && sport !== 'All sports') {
    rows = rows.filter((activity) => formatSportType(activity.sport_type) === sport)
  }

  if (dateFrom) {
    const from = new Date(dateFrom)
    rows = rows.filter((activity) => new Date(activity.activity_date) >= from)
  }

  if (dateTo) {
    const to = new Date(`${dateTo}T23:59:59`)
    rows = rows.filter((activity) => new Date(activity.activity_date) <= to)
  }

  if (minDistanceKm) {
    const minM = Number(minDistanceKm) * 1000
    rows = rows.filter((activity) => (activity.distance_m || 0) >= minM)
  }

  if (hasHr === 'with') {
    rows = rows.filter((activity) => activity.average_heartrate)
  } else if (hasHr === 'without') {
    rows = rows.filter((activity) => !activity.average_heartrate)
  }

  rows.sort((a, b) => {
    if (sort === 'date_asc') return new Date(a.activity_date) - new Date(b.activity_date)
    if (sort === 'distance_desc') return (b.distance_m || 0) - (a.distance_m || 0)
    if (sort === 'distance_asc') return (a.distance_m || 0) - (b.distance_m || 0)
    return new Date(b.activity_date) - new Date(a.activity_date)
  })

  return rows
}
