export const VOLUME_RANGE_OPTIONS = [
  { id: '4w', label: '4 weeks', type: 'week', count: 4 },
  { id: '8w', label: '8 weeks', type: 'week', count: 8 },
  { id: '12w', label: '12 weeks', type: 'week', count: 12 },
  { id: '1m', label: '1 month', type: 'week', count: 4 },
  { id: '6m', label: '6 months', type: 'month', count: 6 },
  { id: '1y', label: '1 year', type: 'month', count: 12 },
]

function startOfMonth(date) {
  return new Date(date.getFullYear(), date.getMonth(), 1)
}

function formatWeekLabel(date) {
  return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}

function formatMonthLabel(date) {
  return date.toLocaleDateString(undefined, { month: 'short', year: '2-digit' })
}

function buildWeeklyBuckets(activities, weekCount, now = new Date()) {
  const end = new Date(now)
  end.setHours(23, 59, 59, 999)
  const lookbackDays = weekCount * 7
  const windowStart = new Date(end)
  windowStart.setDate(windowStart.getDate() - lookbackDays)
  windowStart.setHours(0, 0, 0, 0)

  const buckets = []
  for (let index = 0; index < weekCount; index += 1) {
    const bucketStart = new Date(windowStart)
    bucketStart.setDate(bucketStart.getDate() + index * 7)
    const isLatest = index === weekCount - 1
    const bucketEnd = isLatest ? end : new Date(bucketStart.getTime() + 7 * 24 * 60 * 60 * 1000)

    let totalDistanceM = 0
    let totalMovingS = 0
    let activityCount = 0

    for (const activity of activities) {
      const activityDate = new Date(activity.activity_date)
      if (activityDate < bucketStart) continue
      if (isLatest ? activityDate > bucketEnd : activityDate >= bucketEnd) continue

      totalDistanceM += activity.distance_m || 0
      totalMovingS += activity.moving_time_s || 0
      activityCount += 1
    }

    buckets.push({
      key: bucketStart.toISOString(),
      label: formatWeekLabel(bucketStart),
      total_distance_km: Math.round((totalDistanceM / 1000) * 100) / 100,
      total_moving_hours: Math.round((totalMovingS / 3600) * 100) / 100,
      activity_count: activityCount,
      isCurrent: isLatest,
    })
  }

  return buckets
}

function buildMonthlyBuckets(activities, monthCount, now = new Date()) {
  const buckets = []

  for (let offset = monthCount - 1; offset >= 0; offset -= 1) {
    const bucketStart = startOfMonth(new Date(now.getFullYear(), now.getMonth() - offset, 1))
    const bucketEnd =
      offset === 0
        ? new Date(now)
        : new Date(bucketStart.getFullYear(), bucketStart.getMonth() + 1, 0, 23, 59, 59, 999)

    let totalDistanceM = 0
    let totalMovingS = 0
    let activityCount = 0

    for (const activity of activities) {
      const activityDate = new Date(activity.activity_date)
      if (activityDate < bucketStart || activityDate > bucketEnd) continue
      totalDistanceM += activity.distance_m || 0
      totalMovingS += activity.moving_time_s || 0
      activityCount += 1
    }

    buckets.push({
      key: bucketStart.toISOString(),
      label: formatMonthLabel(bucketStart),
      total_distance_km: Math.round((totalDistanceM / 1000) * 100) / 100,
      total_moving_hours: Math.round((totalMovingS / 3600) * 100) / 100,
      activity_count: activityCount,
      isCurrent: offset === 0,
    })
  }

  return buckets
}

export function buildVolumeHistory(activities, rangeId) {
  const range = VOLUME_RANGE_OPTIONS.find((option) => option.id === rangeId) || VOLUME_RANGE_OPTIONS[1]
  const now = new Date()

  if (range.type === 'month') {
    return { buckets: buildMonthlyBuckets(activities, range.count, now), range }
  }
  return { buckets: buildWeeklyBuckets(activities, range.count, now), range }
}

export function sumVolumeTotals(buckets, mode) {
  const key = mode === 'time' ? 'total_moving_hours' : 'total_distance_km'
  const total = buckets.reduce((sum, bucket) => sum + (bucket[key] || 0), 0)
  const activities = buckets.reduce((sum, bucket) => sum + (bucket.activity_count || 0), 0)
  return { total: Math.round(total * 100) / 100, activities }
}
