import { useMemo } from 'react'
import { motion } from 'framer-motion'
import {
  PRIORITY_GUIDES,
  daysBetween,
  formatSeasonDate,
  isCurrentPhase,
  phaseAccent,
  phaseLabel,
  spanDays,
  todayPositionPct,
} from '../../utils/seasonGuides'

/**
 * Proportional season bar: one clickable segment per phase, a today marker,
 * and a pin for every race that lands inside the plan window.
 */
export default function SeasonTimeline({
  phases = [],
  startDate,
  endDate,
  events = [],
  onSelectPhase,
}) {
  const totalDays = spanDays(startDate, endDate)

  const segments = useMemo(
    () =>
      phases.map((phase, index) => {
        const offset = daysBetween(startDate, phase.start_date)
        const width = (spanDays(phase.start_date, phase.end_date) / totalDays) * 100
        return {
          phase,
          index,
          left: Math.max(0, (offset / totalDays) * 100),
          width: Math.max(1.5, Math.min(width, 100)),
          current: isCurrentPhase(phase),
        }
      }),
    [phases, startDate, totalDays],
  )

  const pins = useMemo(
    () =>
      (events || [])
        .map((event) => {
          const offset = daysBetween(startDate, event.date)
          if (offset < 0 || offset > totalDays) return null
          return { event, left: (offset / totalDays) * 100 }
        })
        .filter(Boolean),
    [events, startDate, totalDays],
  )

  const todayPct = todayPositionPct(startDate, endDate)

  return (
    <div>
      <div className="relative mb-1.5 h-5">
        {pins.map(({ event, left }) => {
          const priority = PRIORITY_GUIDES[event.priority] || PRIORITY_GUIDES.E
          return (
            <div
              key={`pin-${event.id}`}
              className="absolute -translate-x-1/2"
              style={{ left: `${left}%` }}
              title={`${priority.label}: ${event.name} · ${formatSeasonDate(event.date)}`}
            >
              <span
                className={`block h-2.5 w-2.5 rounded-full ring-2 ring-[var(--aal-card)] ${priority.pin}`}
              />
              <span className="sr-only">
                {priority.label} {event.name} on {formatSeasonDate(event.date)}
              </span>
            </div>
          )
        })}
      </div>

      <div className="relative">
        <div className="relative h-6 overflow-hidden rounded-full bg-slate-900/10 dark:bg-white/10">
          {segments.map(({ phase, index, left, width, current }) => {
            const accent = phaseAccent(phase.phase_type)
            return (
              <motion.button
                key={`${phase.id}-${phase.start_date}`}
                type="button"
                onClick={() => onSelectPhase?.(index)}
                title={`${phaseLabel(phase.phase_type)} · ${formatSeasonDate(
                  phase.start_date,
                )} – ${formatSeasonDate(phase.end_date)}`}
                aria-label={`${phaseLabel(phase.phase_type)}, ${phase.week_count} weeks, open details`}
                className={`absolute inset-y-0 cursor-pointer border-r border-[var(--aal-card)]/40 outline-none transition-[filter] last:border-r-0 hover:brightness-110 focus-visible:brightness-125 ${accent.bar} ${
                  current ? '' : 'opacity-75'
                }`}
                style={{ left: `${left}%` }}
                initial={{ width: 0 }}
                animate={{ width: `${width}%` }}
                transition={{
                  duration: 0.5,
                  delay: 0.06 * index,
                  ease: [0.22, 1, 0.36, 1],
                }}
              />
            )
          })}
        </div>

        {todayPct != null ? (
          <motion.div
            className="pointer-events-none absolute -top-1 -bottom-1 w-[2px] rounded-full bg-[var(--aal-ink)]"
            style={{ left: `${todayPct}%` }}
            initial={{ opacity: 0, scaleY: 0.4 }}
            animate={{ opacity: 1, scaleY: 1 }}
            transition={{ duration: 0.35, delay: 0.45 }}
          >
            <span className="absolute -top-5 left-1/2 -translate-x-1/2 whitespace-nowrap rounded-full bg-[var(--aal-ink)] px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wide text-[var(--aal-card)]">
              Today
            </span>
          </motion.div>
        ) : null}
      </div>

      <div className="mt-2 flex items-center justify-between text-[11px] text-[var(--aal-muted)]">
        <span>{formatSeasonDate(startDate)}</span>
        <span className="hidden sm:inline">Tap any block to see what it is for</span>
        <span>{formatSeasonDate(endDate)}</span>
      </div>
    </div>
  )
}
