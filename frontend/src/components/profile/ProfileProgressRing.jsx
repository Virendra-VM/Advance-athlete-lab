export default function ProfileProgressRing({
  percent,
  size = 88,
  stroke = 7,
  label = 'Complete',
  sublabel = null,
}) {
  const radius = (size - stroke) / 2
  const circumference = 2 * Math.PI * radius
  const offset = circumference - (percent / 100) * circumference
  const complete = percent >= 100

  return (
    <div className="flex flex-col items-center gap-2 text-center">
      <div className="relative" style={{ width: size, height: size }}>
        <svg
          width={size}
          height={size}
          viewBox={`0 0 ${size} ${size}`}
          className="-rotate-90"
          aria-hidden
        >
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            stroke="var(--aal-line)"
            strokeWidth={stroke}
          />
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            stroke={complete ? '#22c55e' : 'var(--aal-accent)'}
            strokeWidth={stroke}
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            className="transition-[stroke-dashoffset] duration-700 ease-out"
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="font-display text-xl font-semibold tabular-nums text-[var(--aal-ink)]">
            {percent}%
          </span>
        </div>
      </div>
      <div>
        <p className="text-xs font-semibold uppercase tracking-[0.14em] text-[var(--aal-muted)]">
          {label}
        </p>
        {sublabel ? (
          <p className="mt-0.5 text-xs text-[var(--aal-muted)]">{sublabel}</p>
        ) : null}
      </div>
    </div>
  )
}
