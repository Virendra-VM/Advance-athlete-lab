import { STRESS_SCALE, STRESS_ZONES, stressMarkerPercent, getStressZone } from '../../utils/stressGuides'

export default function StressZoneStrip({ ratio, today, activeId, onSelect, zones = STRESS_ZONES }) {
  const marker = stressMarkerPercent(ratio)
  const current = activeId || getStressZone(ratio, today).id
  const span = STRESS_SCALE.max - STRESS_SCALE.min

  return (
    <div>
      <div className="relative pt-7">
        {marker != null ? (
          <div
            className="absolute top-0 z-10 -translate-x-1/2 text-center"
            style={{ left: `${marker}%` }}
          >
            <p className="text-[11px] font-semibold tabular-nums text-[var(--aal-ink)]">
              {Number(ratio).toFixed(2)}
            </p>
            <div className="mx-auto mt-0.5 h-2 w-0.5 rounded-full bg-[var(--aal-ink)]" />
          </div>
        ) : null}

        <div className="flex h-3 overflow-hidden rounded-full">
          {zones.map((zone) => (
            <button
              key={zone.id}
              type="button"
              title={`${zone.label} (${zone.range})`}
              onClick={() => onSelect?.(zone.id)}
              className={`h-full transition ${
                current === zone.id ? 'opacity-100' : 'opacity-70 hover:opacity-90'
              }`}
              style={{
                width: `${((zone.to - zone.from) / span) * 100}%`,
                backgroundColor: zone.color,
              }}
            />
          ))}
        </div>
      </div>

      <div className="mt-2 flex justify-between text-[10px] font-medium uppercase tracking-[0.12em] text-[var(--aal-muted)]">
        <span>0.70</span>
        <span>0.90</span>
        <span>1.10</span>
        <span>1.25</span>
        <span>1.40</span>
      </div>

      <div className="mt-3 flex flex-wrap gap-2">
        {zones.map((zone) => (
          <button
            key={zone.id}
            type="button"
            onClick={() => onSelect?.(zone.id)}
            className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs transition ${
              current === zone.id
                ? 'border-indigo-300/50 bg-[var(--aal-card)] font-semibold text-[var(--aal-ink)]'
                : 'border-transparent text-[var(--aal-muted)] hover:text-[var(--aal-ink)]'
            }`}
          >
            <span className="h-2 w-2 rounded-full" style={{ backgroundColor: zone.color }} />
            {zone.label}
          </button>
        ))}
      </div>
    </div>
  )
}
