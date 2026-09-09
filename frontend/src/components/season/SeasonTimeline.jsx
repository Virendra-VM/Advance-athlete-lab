import { useCallback, useRef, useState } from 'react'
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
  weekStartFromTimelinePct,
} from '../../utils/seasonGuides'

/**
 * Proportional season bar: clickable segments, drag recovery weeks, today marker,
 * and race pins inside the plan window.
 */
export default function SeasonTimeline({
  phases = [],
  startDate,
  endDate,
  events = [],
  onSelectPhase,
  onShiftPhase,
  shifting = false,
}) {
  const trackRef = useRef(null)
  const [drag, setDrag] = useState(null)

  const totalDays = spanDays(startDate, endDate)

  const segments = phases.map((phase, index) => {
    const offset = daysBetween(startDate, phase.start_date)
    const width = (spanDays(phase.start_date, phase.end_date) / totalDays) * 100
    return {
      phase,
      index,
      left: Math.max(0, (offset / totalDays) * 100),
      width: Math.max(1.5, Math.min(width, 100)),
      current: isCurrentPhase(phase),
      draggable: Boolean(phase.can_drag && onShiftPhase),
    }
  })

  const pins = (events || [])
    .map((event) => {
      const offset = daysBetween(startDate, event.date)
      if (offset < 0 || offset > totalDays) return null
      return { event, left: (offset / totalDays) * 100 }
    })
    .filter(Boolean)

  const todayPct = todayPositionPct(startDate, endDate)

  const pctFromClientX = useCallback(
    (clientX) => {
      const track = trackRef.current
      if (!track) return null
      const rect = track.getBoundingClientRect()
      if (rect.width <= 0) return null
      return Math.max(0, Math.min(100, ((clientX - rect.left) / rect.width) * 100))
    },
    [],
  )

  const finishDrag = useCallback(
    (phase, pct) => {
      if (!phase || pct == null) return
      const target = weekStartFromTimelinePct(startDate, endDate, pct)
      if (target && target !== phase.start_date) {
        onShiftPhase?.(phase.id, target)
      }
    },
    [endDate, onShiftPhase, startDate],
  )

  const onPointerDown = useCallback(
    (event, segment) => {
      if (!segment.draggable || shifting) return
      event.preventDefault()
      event.currentTarget.setPointerCapture(event.pointerId)
      setDrag({
        phaseId: segment.phase.id,
        pointerId: event.pointerId,
        hoverPct: pctFromClientX(event.clientX) ?? segment.left,
      })
    },
    [pctFromClientX, shifting],
  )

  const onPointerMove = useCallback(
    (event) => {
      if (!drag || drag.pointerId !== event.pointerId) return
      const pct = pctFromClientX(event.clientX)
      if (pct != null) setDrag((current) => ({ ...current, hoverPct: pct }))
    },
    [drag, pctFromClientX],
  )

  const onPointerUp = useCallback(
    (event, segment) => {
      if (!drag || drag.phaseId !== segment.phase.id) return
      event.currentTarget.releasePointerCapture(event.pointerId)
      finishDrag(segment.phase, drag.hoverPct)
      setDrag(null)
    },
    [drag, finishDrag],
  )

  const dragHoverPct = drag?.hoverPct ?? null

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

      <div className="relative" ref={trackRef}>
        <div className="relative h-6 overflow-hidden rounded-full bg-slate-900/10 dark:bg-white/10">
          {segments.map(({ phase, index, left, width, current, draggable }) => {
            const accent = phaseAccent(phase.phase_type)
            const isDragging = drag?.phaseId === phase.id
            return (
              <motion.button
                key={`${phase.id}-${phase.start_date}`}
                type="button"
                onClick={() => {
                  if (isDragging) return
                  onSelectPhase?.(index)
                }}
                onPointerDown={(event) => onPointerDown(event, { phase, draggable })}
                onPointerMove={onPointerMove}
                onPointerUp={(event) => onPointerUp(event, { phase })}
                onPointerCancel={(event) => onPointerUp(event, { phase })}
                title={`${phaseLabel(phase.phase_type)} · ${formatSeasonDate(
                  phase.start_date,
                )} – ${formatSeasonDate(phase.end_date)}${
                  draggable ? ' · Drag to reschedule' : ''
                }`}
                aria-label={`${phaseLabel(phase.phase_type)}, ${phase.week_count} weeks${
                  draggable ? ', drag to move' : ', open details'
                }`}
                className={`absolute inset-y-0 border-r border-[var(--aal-card)]/40 outline-none transition-[filter] last:border-r-0 hover:brightness-110 focus-visible:brightness-125 ${accent.bar} ${
                  current ? '' : 'opacity-75'
                } ${draggable ? 'cursor-grab touch-none active:cursor-grabbing' : 'cursor-pointer'} ${
                  isDragging ? 'z-10 brightness-125 ring-2 ring-sage/60' : ''
                } ${shifting ? 'pointer-events-none opacity-60' : ''}`}
                style={{ left: `${left}%` }}
                initial={{ width: 0 }}
                animate={{ width: `${width}%` }}
                transition={{
                  duration: isDragging ? 0 : 0.5,
                  delay: isDragging ? 0 : 0.06 * index,
                  ease: [0.22, 1, 0.36, 1],
                }}
              />
            )
          })}
        </div>

        {dragHoverPct != null ? (
          <div
            className="pointer-events-none absolute -top-1 -bottom-1 w-[2px] rounded-full bg-sage"
            style={{ left: `${dragHoverPct}%` }}
          >
            <span className="absolute -top-5 left-1/2 -translate-x-1/2 whitespace-nowrap rounded-full bg-sage px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wide text-white">
              {formatSeasonDate(weekStartFromTimelinePct(startDate, endDate, dragHoverPct), {
                withYear: false,
              })}
            </span>
          </div>
        ) : null}

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
        <span className="hidden text-center sm:inline">
          Tap a block for details · drag recovery weeks to reschedule
        </span>
        <span>{formatSeasonDate(endDate)}</span>
      </div>
    </div>
  )
}
