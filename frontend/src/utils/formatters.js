export function formatDistanceKm(distanceM) {
  if (distanceM == null) return '—'
  return `${(distanceM / 1000).toFixed(2)} km`
}

/** Parse API timestamps that may be naive UTC (no Z) as UTC. */
export function parseUtcDate(value) {
  if (value == null || value === '') return null
  if (value instanceof Date) return value
  const text = String(value).trim()
  if (!text) return null
  if (/^\d+$/.test(text)) return new Date(Number(text))
  if (/Z$|[+-]\d{2}:?\d{2}$/.test(text)) return new Date(text)
  if (/^\d{4}-\d{2}-\d{2}$/.test(text)) return new Date(`${text}T00:00:00Z`)
  const normalized = text.includes('T') ? text : text.replace(' ', 'T')
  return new Date(`${normalized}Z`)
}

export function formatDuration(seconds) {
  if (seconds == null || Number.isNaN(Number(seconds))) return '—'
  const total = Math.max(0, Math.round(Number(seconds)))
  const hours = Math.floor(total / 3600)
  const minutes = Math.floor((total % 3600) / 60)
  const secs = total % 60
  if (hours > 0) {
    return `${hours}:${String(minutes).padStart(2, '0')}:${String(secs).padStart(2, '0')}`
  }
  return `${minutes}:${String(secs).padStart(2, '0')}`
}

export function formatDurationHours(seconds) {
  return `${(seconds / 3600).toFixed(1)}h`
}

export function formatDate(value) {
  const date = parseUtcDate(value)
  if (!date || Number.isNaN(date.getTime())) return '—'
  return date.toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  })
}

export function formatDateLong(value) {
  const date = parseUtcDate(value)
  if (!date || Number.isNaN(date.getTime())) return '—'
  return date.toLocaleDateString(undefined, {
    weekday: 'short',
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  })
}

export function formatClockTime(value) {
  const date = parseUtcDate(value)
  if (!date || Number.isNaN(date.getTime())) return '—'
  return date.toLocaleTimeString(undefined, {
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function formatDateTime(value) {
  const date = parseUtcDate(value)
  if (!date || Number.isNaN(date.getTime())) return '—'
  return `${formatDate(date)} · ${formatClockTime(date)}`
}

export function toISODateLocal(value = new Date()) {
  const d = value instanceof Date ? value : new Date(value)
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

export function addDaysISO(isoDate, days) {
  const d = new Date(`${isoDate}T12:00:00`)
  d.setDate(d.getDate() + days)
  return toISODateLocal(d)
}
