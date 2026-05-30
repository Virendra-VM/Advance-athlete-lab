export function formatDistanceKm(distanceM) {
  return `${(distanceM / 1000).toFixed(2)} km`
}

export function formatDuration(seconds) {
  const hours = Math.floor(seconds / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  if (hours > 0) return `${hours}h ${minutes}m`
  return `${minutes}m`
}

export function formatDurationHours(seconds) {
  return `${(seconds / 3600).toFixed(1)}h`
}

export function formatDate(value) {
  return new Date(value).toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  })
}
