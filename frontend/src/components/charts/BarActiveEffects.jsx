import { Rectangle } from 'recharts'

/**
 * Unique bar hover: soft sage halo + glowing stroke instead of a washed band.
 */
export default function BarActiveGlow(props) {
  const { x, y, width, height, fill } = props
  if (x == null || y == null || width == null || height == null) return null

  return (
    <g>
      <rect
        x={x - 4}
        y={Math.max(0, y - 6)}
        width={width + 8}
        height={height + 6}
        rx={10}
        fill="rgba(107, 144, 128, 0.2)"
      />
      <Rectangle
        {...props}
        fill={fill}
        stroke="#a7c4b5"
        strokeWidth={2}
        radius={[6, 6, 0, 0]}
        style={{ filter: 'drop-shadow(0 0 12px rgba(107, 144, 128, 0.65))' }}
      />
    </g>
  )
}
