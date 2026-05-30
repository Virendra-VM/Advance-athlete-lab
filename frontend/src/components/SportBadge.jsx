import { formatSportType, getSportBadgeClass } from '../utils/sportTypes'

export default function SportBadge({ sportType, className = '' }) {
  const label = formatSportType(sportType)
  return (
    <span
      className={`inline-flex rounded-full px-2.5 py-1 text-xs font-semibold ${getSportBadgeClass(sportType)} ${className}`}
    >
      {label}
    </span>
  )
}
