import { useMemo, useState } from 'react'
import { motion } from 'framer-motion'
import {
  PHASE_ORDER,
  formatSeasonDate,
  phaseAccent,
  phaseLabel,
  volumeBiasLabel,
} from '../../utils/seasonGuides'

/**
 * One column per week of the season, so the athlete can see the shape of the
 * plan — where the down weeks fall, where volume steps up, and which week they
 * are standing in. The macro bar above shows the phases; this shows the rhythm.
 *
 * Column height encodes volume bias, which is what makes a 3:1 loading pattern
 * visible at a glance instead of buried in a number.
 */

const MIN_HEIGHT_PCT = 22
const MAX_HEIGHT_PCT = 100

function heightFor(bias, maxBias) {
  const value = Number(bias)
  if (!Number.isFinite(value) || value <= 0 || !maxBias) return MIN_HEIGHT_PCT
  const ratio = value / maxBias
  return Math.round(MIN_HEIGHT_PCT + ratio * (MAX_HEIGHT_PCT - MIN_HEIGHT_PCT))
}

function racePin(events) {
  // A-race outranks everything, then B, then whatever else is that week.
  const order = ['A', 'B', 'C', 'D', 'E']
  return (events || [])
    .slice()
    .sort((a, b) => order.indexOf(a.priority) - order.indexOf(b.priority))[0]
}

export default function SeasonWeekStrip({ weeks = [], onSelectPhase, phases = [] }) {
  const [hovered, setHovered] = useState(null)

  const maxBias = useMemo(
    () =>
      weeks.reduce((max, week) => Math.max(max, Number(week.volume_bias) || 0), 0) || 1,
    [weeks],
  )

  const legend = useMemo(() => {
    const present = new Set(weeks.map((week) => week.phase_type))
    return PHASE_ORDER.filter((phaseType) => present.has(phaseType))
  }, [weeks])

  const phaseIndexById = useMemo(() => {
    const map = new Map()
    phases.forEach((phase, index) => map.set(phase.id, index))
    return map
  }, [phases])

  if (!weeks.length) return null

  const active = hovered != null ? weeks[hovered] : null

  return (
    <div>
      <div className="flex items-end gap-[3px] sm:gap-1" role="list">
        {weeks.map((week, index) => {
          const accent = phaseAccent(week.phase_type)
          const pin = racePin(week.events)
          const phaseIndex = phaseIndexById.get(week.phase_id)
          const selectable = phaseIndex != null && onSelectPhase
          return (
            <button
              key={week.week_start}
              type="button"
              role="listitem"
              aria-label={`Week ${week.week_number}, ${formatSeasonDate(week.week_start)}, ${phaseLabel(week.phase_type)}`}
              onClick={() => (selectable ? onSelectPhase(phaseIndex) : null)}
              onMouseEnter={() => setHovered(index)}
              onMouseLeave={() => setHovered((current) => (current === index ? null : current))}
              onFocus={() => setHovered(index)}
              onBlur={() => setHovered((current) => (current === index ? null : current))}
              className="group relative flex h-24 flex-1 cursor-pointer flex-col justify-end outline-none"
            >
              {pin ? (
                <span
                  aria-hidden="true"
                  className={`mx-auto mb-1 h-1.5 w-1.5 shrink-0 rounded-full ${
                    pin.priority === 'A' ? 'bg-amber-400' : 'bg-indigo-400'
                  }`}
                />
              ) : null}
              <motion.span
                aria-hidden="true"
                initial={{ height: `${MIN_HEIGHT_PCT}%`, opacity: 0 }}
                animate={{
                  height: `${heightFor(week.volume_bias, maxBias)}%`,
                  opacity: week.is_past ? 0.4 : 1,
                }}
                transition={{
                  duration: 0.35,
                  delay: Math.min(index * 0.012, 0.4),
                  ease: 'easeOut',
                }}
                className={`w-full rounded-sm ${accent.bar} ${
                  week.is_current
                    ? 'ring-2 ring-offset-1 ring-indigo-500 ring-offset-[var(--aal-card)]'
                    : ''
                } transition-opacity group-hover:opacity-100 group-focus-visible:opacity-100`}
              />
            </button>
          )
        })}
      </div>

      {/* One shared readout rather than a tooltip per column. */}
      <div className="mt-3 min-h-[2.5rem] rounded-lg border border-[var(--aal-line)] bg-[var(--aal-card)]/60 px-3 py-2">
        {active ? (
          <p className="text-xs leading-relaxed text-[var(--aal-muted)]">
            <span className="font-semibold text-[var(--aal-ink)]">
              Week {active.week_number} · {formatSeasonDate(active.week_start)}
            </span>
            {' — '}
            {phaseLabel(active.phase_type)}
            {active.week_in_phase ? ` week ${active.week_in_phase}` : ''}
            {active.volume_bias != null
              ? `, volume ${volumeBiasLabel(active.volume_bias).toLowerCase()}`
              : ''}
            {active.is_current ? ' · this week' : ''}
            {(active.events || []).map((event) => (
              <span key={`${event.name}-${event.date}`} className="block">
                {event.priority}-race: {event.name} on {formatSeasonDate(event.date)}
              </span>
            ))}
          </p>
        ) : (
          <p className="text-xs text-[var(--aal-muted)]">
            Bar height is that week&apos;s volume — the dips are your planned recovery weeks.
            Hover a week for detail, or click to open its phase.
          </p>
        )}
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1.5">
        {legend.map((phaseType) => (
          <span
            key={phaseType}
            className="inline-flex items-center gap-1.5 text-[11px] text-[var(--aal-muted)]"
          >
            <span
              aria-hidden="true"
              className={`h-2 w-2 rounded-sm ${phaseAccent(phaseType).bar}`}
            />
            {phaseLabel(phaseType)}
          </span>
        ))}
      </div>
    </div>
  )
}
