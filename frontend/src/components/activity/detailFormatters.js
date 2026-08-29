import { formatDuration } from '../../utils/formatters'

export function formatPace(minPerKm) {
  if (minPerKm == null || !Number.isFinite(minPerKm) || minPerKm <= 0) return '—'
  const minutes = Math.floor(minPerKm)
  const seconds = Math.round((minPerKm - minutes) * 60)
  return `${minutes}:${String(seconds % 60).padStart(2, '0')}`
}

export function formatLapDuration(seconds) {
  if (seconds == null) return '—'
  return formatDuration(seconds)
}
