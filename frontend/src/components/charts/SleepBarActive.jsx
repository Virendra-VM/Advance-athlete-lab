import { Rectangle } from 'recharts'
import { SLEEP_CHART } from '../../utils/sleepHelpers'

/**
 * Sleep-page bar hover: cool blue halo (Garmin/COROS-like), not global sage glow.
 */
export default function SleepBarActive(props) {
  const { x, y, width, height, fill } = props
  if (x == null || y == null || width == null || height == null) return null

  return (
    <g>
      <rect
        x={x - 3}
        y={Math.max(0, y - 5)}
        width={width + 6}
        height={height + 5}
        rx={8}
        fill={SLEEP_CHART.durationSoft}
      />
      <Rectangle
        {...props}
        fill={fill}
        stroke="#93C5FD"
        strokeWidth={1.5}
        radius={[8, 8, 0, 0]}
        style={{ filter: 'drop-shadow(0 0 10px rgba(91, 141, 239, 0.45))' }}
      />
    </g>
  )
}
