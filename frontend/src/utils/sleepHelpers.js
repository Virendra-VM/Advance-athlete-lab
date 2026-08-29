export const SLEEP_RANGES = [
  { id: 'day', label: 'Day', days: 1 },
  { id: 'week', label: 'Week', days: 7 },
  { id: 'month', label: 'Month', days: 30 },
  { id: 'year', label: 'Year', days: 365 },
]

export const STAGE_COLORS = {
  awake: '#c4a574',
  rem: '#6b9ac4',
  light: '#a4c3b2',
  deep: '#3d5a4c',
}

export function toISODate(value) {
  if (!value) return null
  if (typeof value === 'string') return value.slice(0, 10)
  return null
}

export function addDaysISO(isoDate, days) {
  const date = new Date(`${isoDate}T12:00:00`)
  date.setDate(date.getDate() + days)
  return date.toISOString().slice(0, 10)
}

export function todayISO() {
  return new Date().toISOString().slice(0, 10)
}

export function formatMinutes(value) {
  if (value == null || Number.isNaN(Number(value))) return '—'
  const total = Math.max(0, Math.round(Number(value)))
  const hours = Math.floor(total / 60)
  const minutes = total % 60
  if (hours <= 0) return `${minutes}m`
  return `${hours}h ${minutes.toString().padStart(2, '0')}m`
}

export function formatPct(value, digits = 0) {
  if (value == null || Number.isNaN(Number(value))) return '—'
  return `${Number(value).toFixed(digits)}%`
}

export function formatNumber(value, digits = 0, suffix = '') {
  if (value == null || Number.isNaN(Number(value))) return '—'
  return `${Number(value).toFixed(digits)}${suffix}`
}

export function formatClock(value) {
  if (!value) return '—'
  const match = String(value).match(/(\d{1,2}):(\d{2})/)
  if (!match) return String(value)
  let hour = Number(match[1])
  const minute = match[2]
  const ampm = hour >= 12 ? 'PM' : 'AM'
  hour = hour % 12 || 12
  return `${hour}:${minute} ${ampm}`
}

export function formatDayLabel(isoDate, mode = 'short') {
  if (!isoDate) return '—'
  const date = new Date(`${isoDate}T12:00:00`)
  if (mode === 'weekday') {
    return date.toLocaleDateString(undefined, { weekday: 'short' })
  }
  if (mode === 'full') {
    return date.toLocaleDateString(undefined, {
      weekday: 'long',
      month: 'short',
      day: 'numeric',
    })
  }
  return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}

/** Minutes from an evening anchor so late nights sort correctly. */
export function bedtimeToOffsetMinutes(clock) {
  const match = String(clock || '').match(/(\d{1,2}):(\d{2})/)
  if (!match) return null
  let minutes = Number(match[1]) * 60 + Number(match[2])
  if (minutes < 18 * 60) minutes += 24 * 60
  return minutes
}

export function offsetMinutesToClock(offset) {
  if (offset == null || Number.isNaN(Number(offset))) return null
  let minutes = ((Math.round(Number(offset)) % (24 * 60)) + 24 * 60) % (24 * 60)
  const hour = Math.floor(minutes / 60)
  const minute = minutes % 60
  return `${hour.toString().padStart(2, '0')}:${minute.toString().padStart(2, '0')}`
}

export function stageMinutes(point) {
  const duration = Number(
    point?.meta?.sleep_duration_min ?? point?.secondary ?? point?.duration,
  )
  const deepPct = Number(point?.meta?.deep_sleep_pct ?? point?.deep)
  const lightPct = Number(point?.meta?.light_sleep_pct ?? point?.light)
  const remPct = Number(point?.meta?.rem_sleep_pct ?? point?.rem)
  const awake = Number(point?.meta?.awake_min ?? point?.awake)
  if (!duration || Number.isNaN(duration) || duration <= 0) {
    return {
      deep: null,
      light: null,
      rem: null,
      awake: Number.isNaN(awake) ? null : awake,
      duration: null,
    }
  }
  return {
    duration,
    deep: Number.isNaN(deepPct) ? null : (duration * deepPct) / 100,
    light: Number.isNaN(lightPct) ? null : (duration * lightPct) / 100,
    rem: Number.isNaN(remPct) ? null : (duration * remPct) / 100,
    awake: Number.isNaN(awake) ? null : awake,
  }
}

export function average(values) {
  const nums = values.filter((v) => v != null && !Number.isNaN(Number(v))).map(Number)
  if (!nums.length) return null
  return nums.reduce((a, b) => a + b, 0) / nums.length
}

export function bedtimeConsistency(points) {
  const offsets = (points || [])
    .map((p) => bedtimeToOffsetMinutes(p?.bedtime ?? p?.meta?.bedtime))
    .filter((v) => v != null)
  if (offsets.length < 2) {
    return {
      sampleCount: offsets.length,
      avgBedtime: offsets.length ? offsetMinutesToClock(offsets[0]) : null,
      stdMinutes: null,
      label: offsets.length ? 'Need more nights' : 'No bedtime data',
    }
  }
  const mean = offsets.reduce((a, b) => a + b, 0) / offsets.length
  const variance =
    offsets.reduce((sum, value) => sum + (value - mean) ** 2, 0) / offsets.length
  const std = Math.sqrt(variance)
  let label = 'Variable'
  if (std <= 25) label = 'Consistent'
  else if (std <= 45) label = 'Fair'
  return {
    sampleCount: offsets.length,
    avgBedtime: offsetMinutesToClock(mean),
    stdMinutes: std,
    label,
  }
}

export function latestValuedPoint(points) {
  return [...(points || [])]
    .reverse()
    .find((p) => p.score != null || p.duration != null || p.value != null || p.secondary != null) || null
}

export function enrichSleepPoints(series) {
  return (series?.points || []).map((point) => {
    const stages = stageMinutes(point)
    const date = toISODate(point.date)
    return {
      ...point,
      date,
      labelShort: date?.slice(5) || '',
      score: point.value,
      duration: point.secondary ?? point.meta?.sleep_duration_min ?? null,
      deep: point.meta?.deep_sleep_pct ?? null,
      light: point.meta?.light_sleep_pct ?? null,
      rem: point.meta?.rem_sleep_pct ?? null,
      awake: point.meta?.awake_min ?? null,
      hrv: point.meta?.hrv ?? null,
      sleepHr: point.meta?.sleep_avg_hr ?? null,
      nap: point.meta?.nap_duration_min ?? null,
      bedtime: point.meta?.bedtime ?? null,
      wake: point.meta?.wake_time ?? null,
      hrvAssessment: point.meta?.hrv_assessment ?? null,
      deepMin: stages.deep,
      lightMin: stages.light,
      remMin: stages.rem,
      awakeMin: stages.awake,
    }
  })
}

/** Keep only nights inside the selected view window ending at the latest sample (or today). */
export function slicePointsForView(points, view) {
  const valued = (points || []).filter((p) => p.score != null || p.duration != null)
  if (!valued.length) return []

  if (view === 'day') {
    const latest = valued[valued.length - 1]
    return latest ? [latest] : []
  }

  const days = SLEEP_RANGES.find((item) => item.id === view)?.days || 7
  const end = valued[valued.length - 1].date || todayISO()
  const start = addDaysISO(end, -(days - 1))
  const windowed = valued.filter((p) => p.date >= start && p.date <= end)

  // Year: if history is shorter than 365d, start at first real sample (COROS-like).
  if (view === 'year' && valued.length) {
    const first = valued[0].date
    return valued.filter((p) => p.date >= first && p.date <= end)
  }

  return windowed
}

/** Last N nights before (and excluding) the focused night — for Day compare strip. */
export function previousNights(allPoints, focusDate, count = 7) {
  return (allPoints || [])
    .filter((p) => (p.score != null || p.duration != null) && p.date < focusDate)
    .slice(-count)
}

export function summarizePeriod(points) {
  const list = points || []
  const consistency = bedtimeConsistency(list)
  const avgDeep = average(list.map((p) => p.deep))
  const avgLight = average(list.map((p) => p.light))
  const avgRem = average(list.map((p) => p.rem))
  const avgDuration = average(list.map((p) => p.duration))
  const avgAwake = average(list.map((p) => p.awake))

  return {
    nights: list.length,
    avgScore: average(list.map((p) => p.score)),
    avgDuration,
    avgDeep,
    avgLight,
    avgRem,
    avgAwake,
    avgHrv: average(list.map((p) => p.hrv)),
    avgSleepHr: average(list.map((p) => p.sleepHr)),
    avgNap: average(list.map((p) => p.nap)),
    totalSleep: list.reduce((sum, p) => sum + (Number(p.duration) || 0), 0) || null,
    consistency,
    // Average stage minutes for period pie/bar
    deepMin:
      avgDuration != null && avgDeep != null ? (avgDuration * avgDeep) / 100 : null,
    lightMin:
      avgDuration != null && avgLight != null ? (avgDuration * avgLight) / 100 : null,
    remMin: avgDuration != null && avgRem != null ? (avgDuration * avgRem) / 100 : null,
    awakeMin: avgAwake,
    from: list[0]?.date || null,
    to: list[list.length - 1]?.date || null,
  }
}

/** Bucket daily points into ISO weeks for Year charts. */
export function aggregateByWeek(points) {
  const buckets = new Map()
  for (const point of points || []) {
    if (!point.date) continue
    const d = new Date(`${point.date}T12:00:00`)
    const day = (d.getDay() + 6) % 7
    d.setDate(d.getDate() - day)
    const key = d.toISOString().slice(0, 10)
    if (!buckets.has(key)) buckets.set(key, [])
    buckets.get(key).push(point)
  }
  return [...buckets.entries()].map(([weekStart, rows]) => {
    const summary = summarizePeriod(rows)
    return {
      date: weekStart,
      labelShort: weekStart.slice(5),
      score: summary.avgScore,
      duration: summary.avgDuration,
      deep: summary.avgDeep,
      light: summary.avgLight,
      rem: summary.avgRem,
      awake: summary.avgAwake,
      hrv: summary.avgHrv,
      sleepHr: summary.avgSleepHr,
      deepMin: summary.deepMin,
      lightMin: summary.lightMin,
      remMin: summary.remMin,
      awakeMin: summary.awakeMin,
      nights: summary.nights,
    }
  })
}

export function periodTitle(view, summary, night) {
  if (view === 'day') {
    return night?.date ? formatDayLabel(night.date, 'full') : 'Last night'
  }
  if (!summary?.from || !summary?.to) {
    return view === 'week' ? 'This week' : view === 'month' ? 'This month' : 'This year'
  }
  if (view === 'week') {
    return `${formatDayLabel(summary.from)} – ${formatDayLabel(summary.to)}`
  }
  if (view === 'month') {
    return `${formatDayLabel(summary.from)} – ${formatDayLabel(summary.to)}`
  }
  return `${formatDayLabel(summary.from)} – ${formatDayLabel(summary.to)}`
}
