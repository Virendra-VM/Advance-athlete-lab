/**
 * Build COROS-style distance splits from timeline points.
 */
export function buildDistanceSplits(points = [], splitDistanceM = 1000) {
  if (!points?.length || !splitDistanceM || splitDistanceM <= 0) return []

  const sorted = [...points]
    .filter((p) => p != null && p.distance_m != null)
    .sort((a, b) => Number(a.distance_m) - Number(b.distance_m))

  if (sorted.length < 2) return []
  const maxDistance = Number(sorted[sorted.length - 1].distance_m || 0)
  if (maxDistance < splitDistanceM * 0.15) return []

  const avg = (arr) => (arr.length ? arr.reduce((a, b) => a + b, 0) / arr.length : null)
  const max = (arr) => (arr.length ? Math.max(...arr) : null)

  function approxNp(powerValues) {
    if (!powerValues.length) return null
    const window = Math.min(30, powerValues.length)
    if (window < 5) return avg(powerValues)
    const raised = []
    for (let i = window - 1; i < powerValues.length; i += 1) {
      const slice = powerValues.slice(i - window + 1, i + 1)
      const mean = avg(slice)
      raised.push(mean ** 4)
    }
    if (!raised.length) return avg(powerValues)
    return Math.pow(raised.reduce((a, b) => a + b, 0) / raised.length, 0.25)
  }

  function metricsForSlice(slice, index, label, isPartial) {
    if (!slice.length) return null
    const start = slice[0]
    const end = slice[slice.length - 1]
    const distance_m = Math.max(0, Number(end.distance_m) - Number(start.distance_m))
    const duration_s = Math.max(0, Number(end.elapsed_s || 0) - Number(start.elapsed_s || 0))
    if (distance_m < 5 && duration_s < 2) return null

    const hrs = slice.map((p) => p.heart_rate).filter((v) => v != null).map(Number)
    const powers = slice.map((p) => p.power).filter((v) => v != null).map(Number)
    const cadences = slice.map((p) => p.cadence).filter((v) => v != null).map(Number)
    const speeds = slice
      .map((p) => (p.speed_mps != null ? Number(p.speed_mps) * 3.6 : null))
      .filter((v) => v != null)

    return {
      index,
      label,
      distance_m,
      duration_s,
      total_time_s: Number(end.elapsed_s || 0),
      avg_hr: avg(hrs),
      max_hr: max(hrs),
      avg_pace: distance_m > 0 && duration_s > 0 ? duration_s / 60 / (distance_m / 1000) : null,
      avg_speed:
        avg(speeds) ??
        (distance_m > 0 && duration_s > 0 ? (distance_m / duration_s) * 3.6 : null),
      avg_power: avg(powers),
      normalized_power: approxNp(powers),
      avg_cadence: avg(cadences),
      effort_accuracy: null,
      is_partial: isPartial,
    }
  }

  const splits = []
  let startIdx = 0
  let target = splitDistanceM
  let index = 1

  for (let i = 0; i < sorted.length; i += 1) {
    const distance = Number(sorted[i].distance_m || 0)
    if (distance < target) continue

    const slice = sorted.slice(startIdx, i + 1)
    const km = splitDistanceM / 1000
    const label = `${km % 1 === 0 ? km : km.toFixed(1)} km`
    const row = metricsForSlice(slice, index, label, false)
    if (row) {
      splits.push(row)
      index += 1
    }
    startIdx = i
    target += splitDistanceM
  }

  const leftover = maxDistance - (target - splitDistanceM)
  if (leftover > splitDistanceM * 0.05 && startIdx < sorted.length - 1) {
    const slice = sorted.slice(startIdx)
    const km = leftover / 1000
    const label = `Partial ${km < 1 ? km.toFixed(2) : km.toFixed(1)} km`
    const row = metricsForSlice(slice, index, label, true)
    if (row) splits.push(row)
  }

  return splits
}

export function splitModeOptions(family) {
  if (family === 'ride') {
    return [
      { id: 'laps', label: 'Laps' },
      { id: '1km', label: '1 km', meters: 1000 },
      { id: '5km', label: '5 km', meters: 5000 },
      { id: '10km', label: '10 km', meters: 10000 },
    ]
  }
  if (family === 'swim') {
    return [
      { id: 'laps', label: 'Laps' },
      { id: '100m', label: '100 m', meters: 100 },
      { id: '200m', label: '200 m', meters: 200 },
      { id: '500m', label: '500 m', meters: 500 },
    ]
  }
  return [
    { id: 'laps', label: 'Laps' },
    { id: '1km', label: '1 km', meters: 1000 },
    { id: '5km', label: '5 km', meters: 5000 },
    { id: '10km', label: '10 km', meters: 10000 },
  ]
}
