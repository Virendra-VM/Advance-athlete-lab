import { useState } from 'react'
import { CalendarPlus, ChevronDown, Pin, ShieldCheck, Sparkles } from 'lucide-react'
import LoadingDots from '../ui/LoadingDots'
import SectionCard from '../ui/SectionCard'
import { addDaysISO, formatDistanceKm, toISODateLocal } from '../../utils/formatters'

const REST_TYPES = new Set(['rest', 'mobility'])
const HARD_TYPES = new Set(['intervals', 'threshold', 'tempo', 'hills', 'speed', 'race'])

function dayLabel(iso) {
  return new Date(`${iso}T12:00:00`).toLocaleDateString(undefined, {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
  })
}

function sessionTone(sessionType) {
  const type = String(sessionType || '').toLowerCase()
  if (REST_TYPES.has(type)) return 'text-[var(--aal-muted)]'
  if (HARD_TYPES.has(type)) return 'text-amber-status'
  return 'text-sage'
}

function WorkoutRow({ workout }) {
  const [open, setOpen] = useState(false)
  const hasDetail = Boolean(workout.description || (workout.structure || []).length)
  const done = Boolean(workout.completed_activity_id)

  return (
    <div className="rounded-xl border border-[var(--aal-line)] bg-[var(--aal-bg)]">
      <button
        type="button"
        onClick={() => hasDetail && setOpen((value) => !value)}
        className="flex w-full items-start justify-between gap-3 px-3 py-2.5 text-left"
      >
        <div className="min-w-0">
          <p
            className={`text-[10px] font-semibold uppercase tracking-[0.16em] ${sessionTone(
              workout.session_type,
            )}`}
          >
            {workout.session_type || 'session'}
            {done ? ' · completed' : ''}
          </p>
          <p className="mt-0.5 truncate font-medium">{workout.title || 'Session'}</p>
          <p className="text-sm text-[var(--aal-muted)]">
            {[
              workout.sport,
              workout.duration_min ? `${Math.round(workout.duration_min)} min` : null,
              workout.distance_m ? formatDistanceKm(workout.distance_m) : null,
              workout.intensity,
            ]
              .filter(Boolean)
              .join(' · ')}
          </p>
        </div>
        {hasDetail ? (
          <ChevronDown
            className={`mt-1 h-4 w-4 shrink-0 text-[var(--aal-muted)] transition ${
              open ? 'rotate-180' : ''
            }`}
          />
        ) : null}
      </button>

      {open ? (
        <div className="border-t border-[var(--aal-line)] px-3 py-3 text-sm">
          {workout.description ? <p>{workout.description}</p> : null}
          {(workout.structure || []).length ? (
            <ul className="mt-3 space-y-1">
              {workout.structure.map((segment, index) => (
                <li
                  key={`${segment.segment}-${index}`}
                  className="flex justify-between gap-3 text-[var(--aal-muted)]"
                >
                  <span>{segment.segment}</span>
                  <span>
                    {[
                      segment.duration_min ? `${Math.round(segment.duration_min)} min` : null,
                      segment.intensity,
                    ]
                      .filter(Boolean)
                      .join(' · ')}
                  </span>
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      ) : null}
    </div>
  )
}

function PlanBody({ plan, weekStart, loading, compact }) {
  const workouts = plan?.plan?.workouts || []
  const byDate = new Map()
  for (const workout of workouts) {
    const key = String(workout.date).slice(0, 10)
    if (!byDate.has(key)) byDate.set(key, [])
    byDate.get(key).push(workout)
  }
  const today = toISODateLocal()
  const days = Array.from({ length: 7 }, (_, index) => addDaysISO(weekStart, index)).filter(
    (iso) => !compact || iso >= today || (byDate.get(iso) || []).length,
  )
  const skipped = compact
    ? Array.from({ length: 7 }, (_, index) => addDaysISO(weekStart, index)).filter(
        (iso) => iso < today && !(byDate.get(iso) || []).length,
      ).length
    : 0
  const totalMinutes = workouts
    .filter((workout) => !REST_TYPES.has(String(workout.session_type).toLowerCase()))
    .reduce((sum, workout) => sum + (workout.duration_min || 0), 0)
  const adjustments = (plan?.safety_issues || []).filter((issue) => issue.level !== 'blocking')

  if (loading) {
    return <LoadingDots label="Loading your week…" />
  }

  if (!workouts.length) {
    return (
      <p className="rounded-xl border border-dashed border-[var(--aal-line)] px-3 py-4 text-sm text-[var(--aal-muted)]">
        No week built yet. Generate this week from the bar below — it stays a draft until you add
        it to Schedule.
      </p>
    )
  }

  return (
    <>
      <div className="mb-3 flex flex-wrap gap-x-5 gap-y-1 text-sm text-[var(--aal-muted)]">
        <span>
          {workouts.filter((w) => !REST_TYPES.has(String(w.session_type).toLowerCase())).length}{' '}
          sessions
        </span>
        <span>{Math.round(totalMinutes)} min planned</span>
        {plan?.plan?.focus ? <span>Focus: {plan.plan.focus}</span> : null}
        {plan?.provider ? (
          <span>{plan.provider === 'rules' ? 'Built from rules' : `via ${plan.provider}`}</span>
        ) : null}
        {plan?.on_schedule ? <span className="text-sage">On schedule</span> : <span>Draft</span>}
      </div>

      {skipped ? (
        <p className="mb-2 text-xs text-[var(--aal-muted)]">
          {skipped} earlier day{skipped === 1 ? '' : 's'} this week already passed.
        </p>
      ) : null}

      <div className="space-y-2">
        {days.map((iso) => {
          const dayWorkouts = byDate.get(iso) || []
          const isToday = iso === today
          return (
            <div key={iso} className="grid gap-2 sm:grid-cols-[7.5rem_1fr] sm:items-start">
              <p
                className={`pt-1 text-xs font-semibold uppercase tracking-wide ${
                  isToday ? 'text-sage' : 'text-[var(--aal-muted)]'
                }`}
              >
                {isToday ? 'Today · ' : ''}
                {dayLabel(iso)}
              </p>
              {dayWorkouts.length ? (
                <div className="space-y-2">
                  {dayWorkouts.map((workout, index) => (
                    <WorkoutRow key={workout.id ?? `${iso}-${index}`} workout={workout} />
                  ))}
                </div>
              ) : (
                <p className="rounded-xl border border-dashed border-[var(--aal-line)] px-3 py-2.5 text-sm text-[var(--aal-muted)]">
                  Rest
                </p>
              )}
            </div>
          )
        })}
      </div>

      {plan?.plan?.coach_notes ? (
        <p className="mt-4 rounded-xl border border-[var(--aal-line)] bg-[var(--aal-bg)] px-3 py-3 text-sm">
          {plan.plan.coach_notes}
        </p>
      ) : null}

      {adjustments.length ? (
        <div className="mt-4">
          <p className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.16em] text-[var(--aal-muted)]">
            <ShieldCheck className="h-3.5 w-3.5 text-sage" />
            Safety adjustments
          </p>
          <ul className="space-y-1 text-sm text-[var(--aal-muted)]">
            {adjustments.map((issue) => (
              <li key={`${issue.code}-${issue.message}`}>· {issue.message}</li>
            ))}
          </ul>
        </div>
      ) : null}

      {(plan?.generation_notes || []).length ? (
        <ul className="mt-3 space-y-1 text-xs text-[var(--aal-muted)]">
          {plan.generation_notes.map((note) => (
            <li key={note}>{note}</li>
          ))}
        </ul>
      ) : null}

      {(plan?.citations || []).length ? (
        <div className="mt-4 border-t border-[var(--aal-line)] pt-3">
          <p className="mb-2 text-xs font-semibold uppercase tracking-[0.16em] text-[var(--aal-muted)]">
            Evidence used
          </p>
          <ul className="space-y-1 text-xs text-[var(--aal-muted)]">
            {plan.citations.map((citation) => (
              <li key={citation.slug || citation.title}>
                {citation.url ? (
                  <a
                    href={citation.url}
                    target="_blank"
                    rel="noreferrer"
                    className="underline decoration-dotted"
                  >
                    {citation.title}
                  </a>
                ) : (
                  citation.title
                )}
                {citation.year ? ` (${citation.year})` : ''}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </>
  )
}

function PlanActions({
  plan,
  generating,
  publishing,
  onGenerate,
  onAddToSchedule,
  canGenerate,
}) {
  const workouts = plan?.plan?.workouts || []
  return (
    <div className="flex flex-wrap items-center gap-2">
      <button
        type="button"
        onClick={onGenerate}
        disabled={generating || publishing || !canGenerate}
        className="inline-flex items-center gap-2 rounded-xl bg-sage px-3 py-2 text-sm font-semibold text-white disabled:opacity-60"
      >
        <Sparkles className={`h-4 w-4 ${generating ? 'sync-spin' : ''}`} />
        {generating ? 'Building…' : workouts.length ? 'Rebuild week' : 'Generate week'}
      </button>
      <button
        type="button"
        onClick={onAddToSchedule}
        disabled={
          generating || publishing || !plan?.plan_id || !workouts.length || Boolean(plan?.on_schedule)
        }
        className="inline-flex items-center gap-2 rounded-xl border border-[var(--aal-line)] bg-[var(--aal-card)] px-3 py-2 text-sm font-semibold disabled:opacity-60"
      >
        <CalendarPlus className={`h-4 w-4 ${publishing ? 'sync-spin' : ''}`} />
        {publishing ? 'Adding…' : plan?.on_schedule ? 'On schedule' : 'Add to Schedule'}
      </button>
    </div>
  )
}

export default function WeekPlan({
  plan,
  weekStart,
  loading,
  generating,
  publishing,
  onGenerate,
  onAddToSchedule,
  canGenerate,
  embedded = false,
  pinned = false,
  onPin = null,
}) {
  const title = plan?.plan?.title || `Week of ${dayLabel(weekStart)}`
  const subtitle =
    plan?.plan?.summary ||
    'This week only — generate a plan, then add it to Schedule if you want it on the calendar.'

  if (embedded) {
    return (
      <div className="rounded-2xl border border-sage/25 bg-[var(--aal-card)] p-3 shadow-sm sm:p-4">
        <div className="mb-3 flex items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-sage">
              This week
            </p>
            <h3 className="mt-1 text-base font-semibold text-[var(--aal-ink)]">{title}</h3>
            <p className="mt-0.5 text-sm text-[var(--aal-muted)]">{subtitle}</p>
          </div>
          <div className="flex shrink-0 items-center gap-2">
            {onAddToSchedule && (plan?.plan?.workouts || []).length ? (
              <button
                type="button"
                onClick={onAddToSchedule}
                disabled={generating || publishing || !plan?.plan_id || Boolean(plan?.on_schedule)}
                className="inline-flex items-center gap-2 rounded-xl bg-sage px-3 py-2 text-sm font-semibold text-white disabled:opacity-60"
              >
                <CalendarPlus className={`h-4 w-4 ${publishing ? 'sync-spin' : ''}`} />
                {publishing
                  ? 'Saving…'
                  : plan?.on_schedule
                    ? 'On schedule'
                    : 'Add to Schedule'}
              </button>
            ) : null}
            {onPin ? (
              <button
                type="button"
                onClick={onPin}
                className={`inline-flex shrink-0 items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-xs font-medium transition ${
                  pinned
                    ? 'border-sage/40 bg-sage/10 text-sage'
                    : 'border-[var(--aal-line)] text-[var(--aal-muted)] hover:text-[var(--aal-ink)]'
                }`}
                aria-pressed={pinned}
                aria-label={pinned ? 'Unpin this week' : 'Pin this week'}
              >
                <Pin className={`h-3.5 w-3.5 ${pinned ? 'fill-current' : ''}`} />
                {pinned ? 'Pinned' : 'Pin'}
              </button>
            ) : null}
          </div>
        </div>
        {generating ? (
          <LoadingDots label="Building this week…" />
        ) : (
          <PlanBody plan={plan} weekStart={weekStart} loading={loading} compact />
        )}
      </div>
    )
  }

  return (
    <SectionCard
      title={title}
      subtitle={subtitle}
      actions={
        <PlanActions
          plan={plan}
          generating={generating}
          publishing={publishing}
          onGenerate={onGenerate}
          onAddToSchedule={onAddToSchedule}
          canGenerate={canGenerate}
        />
      }
    >
      <PlanBody plan={plan} weekStart={weekStart} loading={loading} compact={false} />
    </SectionCard>
  )
}

export { PlanActions }
