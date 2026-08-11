import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import {
  Bike,
  CalendarDays,
  ChevronLeft,
  ChevronRight,
  List,
  RefreshCw,
  X,
} from 'lucide-react'
import { listActivities, dedupeActivities } from '../api/activities'
import {
  getCorosOverview,
  getCorosSchedule,
  getCorosSyncStatus,
  startCorosSync,
} from '../api/coros'
import { useAuth } from '../context/AuthContext'
import AppShell from '../components/layout/AppShell'
import EmptyState from '../components/ui/EmptyState'
import LoadingDots from '../components/ui/LoadingDots'
import PageHeader from '../components/ui/PageHeader'
import {
  addDaysISO,
  formatDistanceKm,
  formatDuration,
  toISODateLocal,
} from '../utils/formatters'

function startOfWeekMonday(isoDate) {
  const d = new Date(`${isoDate}T12:00:00`)
  const day = (d.getDay() + 6) % 7
  d.setDate(d.getDate() - day)
  return toISODateLocal(d)
}

function monthMatrix(year, monthIndex) {
  const first = new Date(year, monthIndex, 1)
  const start = startOfWeekMonday(toISODateLocal(first))
  const weeks = []
  let cursor = start
  for (let w = 0; w < 6; w += 1) {
    const week = []
    for (let d = 0; d < 7; d += 1) {
      week.push(cursor)
      cursor = addDaysISO(cursor, 1)
    }
    weeks.push(week)
  }
  return weeks
}

function PlanDetailModal({ plan, onClose, navigate }) {
  if (!plan) return null
  const completed = plan.status === 'completed' || plan.completed_activity_id
  return (
    <div
      className="fixed inset-0 z-[80] flex items-end justify-center bg-black/45 p-4 sm:items-center"
      onClick={onClose}
      role="presentation"
    >
      <div
        role="dialog"
        aria-modal="true"
        className="w-full max-w-md rounded-2xl border border-[var(--aal-line)] bg-[var(--aal-card)] p-6 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-start justify-between gap-3">
          <div>
            <p
              className={`text-[10px] font-semibold uppercase tracking-[0.18em] ${
                completed ? 'text-sage' : 'text-amber-status'
              }`}
            >
              {completed ? 'Completed plan' : 'Planned workout'}
            </p>
            <h2 className="mt-1 text-xl font-bold">{plan.title || 'Workout'}</h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg border border-[var(--aal-line)] p-2 text-[var(--aal-muted)]"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
        <dl className="space-y-3 text-sm">
          <div className="flex justify-between gap-4">
            <dt className="text-[var(--aal-muted)]">Date</dt>
            <dd className="font-medium">{plan.schedule_date}</dd>
          </div>
          <div className="flex justify-between gap-4">
            <dt className="text-[var(--aal-muted)]">Sport</dt>
            <dd className="font-medium">{plan.sport_type || '—'}</dd>
          </div>
          <div className="flex justify-between gap-4">
            <dt className="text-[var(--aal-muted)]">Estimated time</dt>
            <dd className="font-medium">
              {plan.duration_min != null ? `${Math.round(plan.duration_min)} min` : '—'}
            </dd>
          </div>
          <div className="flex justify-between gap-4">
            <dt className="text-[var(--aal-muted)]">Estimated distance</dt>
            <dd className="font-medium">
              {plan.distance_m != null ? formatDistanceKm(plan.distance_m) : '—'}
            </dd>
          </div>
          {completed ? (
            <>
              <div className="flex justify-between gap-4">
                <dt className="text-[var(--aal-muted)]">Completed as</dt>
                <dd className="font-medium text-right">
                  {plan.completed_activity_name || 'Activity'}
                  {plan.completed_activity_provider
                    ? ` · ${String(plan.completed_activity_provider).toUpperCase()}`
                    : ''}
                </dd>
              </div>
              <div className="flex justify-between gap-4">
                <dt className="text-[var(--aal-muted)]">Actual</dt>
                <dd className="font-medium">
                  {formatDistanceKm(plan.completed_distance_m)}
                  {' · '}
                  {formatDuration(plan.completed_moving_time_s)}
                </dd>
              </div>
            </>
          ) : null}
        </dl>
        {completed && plan.completed_activity_id ? (
          <button
            type="button"
            className="mt-5 w-full rounded-xl bg-sage px-4 py-2.5 text-sm font-semibold text-white"
            onClick={() => {
              onClose()
              navigate(`/activities/${plan.completed_activity_id}`)
            }}
          >
            Open activity
          </button>
        ) : null}
      </div>
    </div>
  )
}

function dayEntries(plans, activities) {
  const openPlans = (plans || []).filter(
    (plan) => !(plan.status === 'completed' || plan.completed_activity_id),
  )
  const completedPlans = (plans || []).filter(
    (plan) => plan.status === 'completed' || plan.completed_activity_id,
  )
  const linkedIds = new Set(
    completedPlans.map((plan) => plan.completed_activity_id).filter(Boolean),
  )
  const unmatchedActivities = (activities || []).filter((activity) => !linkedIds.has(activity.id))
  return { openPlans, completedPlans, unmatchedActivities }
}

function DaySection({ isoDate, plans, activities, today, onPlanClick, navigate }) {
  const isToday = isoDate === today
  const label = new Date(`${isoDate}T12:00:00`).toLocaleDateString(undefined, {
    weekday: 'long',
    month: 'short',
    day: 'numeric',
  })
  const { openPlans, completedPlans, unmatchedActivities } = dayEntries(plans, activities)
  const empty =
    openPlans.length === 0 && completedPlans.length === 0 && unmatchedActivities.length === 0

  return (
    <section
      id={`day-${isoDate}`}
      className={`scroll-mt-4 w-full rounded-2xl border px-4 py-4 sm:px-5 ${
        isToday
          ? 'border-sage/40 bg-sage/5'
          : 'border-[var(--aal-line)] bg-[var(--aal-card)]'
      }`}
    >
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-sm font-semibold">
          {label}
          {isToday ? <span className="ml-2 text-sage">Today</span> : null}
        </h3>
        <span className="text-xs text-[var(--aal-muted)]">{isoDate}</span>
      </div>

      {empty ? (
        <p className="text-sm text-[var(--aal-muted)]">Rest / no sessions</p>
      ) : (
        <ul className="space-y-2">
          {openPlans.map((plan) => (
            <li key={`plan-${plan.external_id}-${plan.schedule_date}`}>
              <button
                type="button"
                onClick={() => onPlanClick(plan)}
                className="flex w-full items-center justify-between rounded-xl border border-dashed border-[var(--aal-line)] bg-[var(--aal-bg)] px-3 py-3 text-left transition hover:border-sage/50"
              >
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wide text-amber-status">
                    Planned
                  </p>
                  <p className="font-medium">{plan.title || 'Planned workout'}</p>
                  <p className="text-sm text-[var(--aal-muted)]">
                    {plan.sport_type || 'Workout'}
                    {plan.duration_min != null ? ` · ${Math.round(plan.duration_min)} min` : ''}
                  </p>
                </div>
                <CalendarDays className="h-4 w-4 text-[var(--aal-muted)]" />
              </button>
            </li>
          ))}
          {completedPlans.map((plan) => (
            <li key={`done-plan-${plan.external_id}-${plan.schedule_date}`}>
              <button
                type="button"
                onClick={() => {
                  if (plan.completed_activity_id) {
                    navigate(`/activities/${plan.completed_activity_id}`)
                  } else {
                    onPlanClick(plan)
                  }
                }}
                className="flex w-full items-center justify-between rounded-xl border border-[var(--aal-line)] bg-[var(--aal-bg)] px-3 py-3 text-left transition hover:border-sage/50"
              >
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wide text-sage">
                    Completed
                  </p>
                  <p className="font-medium">
                    {plan.completed_activity_name || plan.title || 'Completed workout'}
                  </p>
                  <p className="text-sm text-[var(--aal-muted)]">
                    {plan.sport_type || 'Workout'}
                    {plan.completed_distance_m != null
                      ? ` · ${formatDistanceKm(plan.completed_distance_m)}`
                      : ''}
                    {plan.completed_moving_time_s != null
                      ? ` · ${formatDuration(plan.completed_moving_time_s)}`
                      : ''}
                    {plan.title ? ` · from plan “${plan.title}”` : ''}
                  </p>
                </div>
                <Bike className="h-4 w-4 text-sage" />
              </button>
            </li>
          ))}
          {unmatchedActivities.map((activity) => (
            <li key={`act-${activity.id}`}>
              <button
                type="button"
                onClick={() => navigate(`/activities/${activity.id}`)}
                className="flex w-full items-center justify-between rounded-xl border border-[var(--aal-line)] bg-[var(--aal-bg)] px-3 py-3 text-left transition hover:border-sage/50"
              >
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wide text-sage">
                    Completed
                  </p>
                  <p className="font-medium">{activity.name}</p>
                  <p className="text-sm text-[var(--aal-muted)]">
                    {activity.sport_type || 'Activity'}
                    {` · ${formatDistanceKm(activity.distance_m)}`}
                    {` · ${formatDuration(activity.moving_time_s)}`}
                  </p>
                </div>
                <Bike className="h-4 w-4 text-sage" />
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

export default function SchedulePage() {
  const { profile } = useAuth()
  const navigate = useNavigate()
  const today = toISODateLocal()
  const [mode, setMode] = useState('timeline') // timeline | calendar
  const [calMode, setCalMode] = useState('month') // month | week
  const [anchorMonth, setAnchorMonth] = useState(() => {
    const d = new Date()
    return { year: d.getFullYear(), month: d.getMonth() }
  })
  const [weekStart, setWeekStart] = useState(() => startOfWeekMonday(today))
  const [connected, setConnected] = useState(false)
  const [plans, setPlans] = useState([])
  const [activities, setActivities] = useState([])
  const [loading, setLoading] = useState(true)
  const [syncing, setSyncing] = useState(false)
  const [error, setError] = useState('')
  const [selectedPlan, setSelectedPlan] = useState(null)
  const scrollRef = useRef(null)

  const fromISO = useMemo(() => addDaysISO(today, -120), [today])
  const toISO = useMemo(() => addDaysISO(today, 90), [today])

  async function loadData() {
    if (!profile?.id) return
    setLoading(true)
    setError('')
    try {
      // Hide Strava↔COROS duplicates before reading the schedule.
      try {
        await dedupeActivities()
      } catch {
        // Non-fatal — schedule still loads even if dedupe fails.
      }
      const overview = await getCorosOverview()
      setConnected(!!overview.connected)
      const [scheduleRows, activityPage] = await Promise.all([
        overview.connected
          ? getCorosSchedule(fromISO, toISO)
          : Promise.resolve([]),
        listActivities(profile.id, {
          from: fromISO,
          to: toISO,
          page: 1,
          page_size: 500,
          sort: 'date_asc',
        }),
      ])
      setPlans(scheduleRows || [])
      setActivities(activityPage.items || [])
    } catch (err) {
      setError(err.message || 'Failed to load schedule.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadData()
  }, [profile?.id])

  function scrollTimelineToToday() {
    const container = scrollRef.current
    const node = document.getElementById(`day-${today}`)
    if (!container || !node) return
    const cRect = container.getBoundingClientRect()
    const nRect = node.getBoundingClientRect()
    const top = container.scrollTop + (nRect.top - cRect.top) - 12
    container.scrollTo({ top: Math.max(0, top), behavior: 'auto' })
  }

  // Always land on today when timeline is shown (including after leaving calendar).
  useEffect(() => {
    if (loading || mode !== 'timeline') return undefined
    const frame = window.requestAnimationFrame(() => {
      scrollTimelineToToday()
    })
    const timeout = window.setTimeout(scrollTimelineToToday, 80)
    return () => {
      window.cancelAnimationFrame(frame)
      window.clearTimeout(timeout)
    }
  }, [loading, mode, today])

  async function handleSync() {
    setSyncing(true)
    setError('')
    try {
      await startCorosSync()
      const started = Date.now()
      while (Date.now() - started < 120000) {
        await new Promise((r) => setTimeout(r, 1200))
        const status = await getCorosSyncStatus()
        if (!status.running) break
      }
      await loadData()
    } catch (err) {
      setError(err.message || 'Sync failed.')
    } finally {
      setSyncing(false)
    }
  }

  const plansByDate = useMemo(() => {
    const map = new Map()
    for (const plan of plans) {
      const key = String(plan.schedule_date).slice(0, 10)
      if (!map.has(key)) map.set(key, [])
      map.get(key).push(plan)
    }
    return map
  }, [plans])

  const activitiesByDate = useMemo(() => {
    const map = new Map()
    for (const activity of activities) {
      const key = toISODateLocal(activity.activity_date)
      if (!map.has(key)) map.set(key, [])
      map.get(key).push(activity)
    }
    return map
  }, [activities])

  const timelineDays = useMemo(() => {
    const days = []
    let cursor = fromISO
    while (cursor <= toISO) {
      days.push(cursor)
      cursor = addDaysISO(cursor, 1)
    }
    return days
  }, [fromISO, toISO])

  const monthWeeks = useMemo(
    () => monthMatrix(anchorMonth.year, anchorMonth.month),
    [anchorMonth],
  )

  const weekDays = useMemo(() => {
    return Array.from({ length: 7 }, (_, i) => addDaysISO(weekStart, i))
  }, [weekStart])

  function renderCalendarCell(isoDate) {
    const inMonth =
      calMode === 'week' ||
      (new Date(`${isoDate}T12:00:00`).getMonth() === anchorMonth.month &&
        new Date(`${isoDate}T12:00:00`).getFullYear() === anchorMonth.year)
    const dayPlans = plansByDate.get(isoDate) || []
    const dayActs = activitiesByDate.get(isoDate) || []
    const { openPlans, completedPlans, unmatchedActivities } = dayEntries(dayPlans, dayActs)
    const isToday = isoDate === today
    const chips = [
      ...openPlans.map((plan) => ({
        key: `p-${plan.external_id}`,
        label: plan.title || 'Plan',
        kind: 'planned',
        onClick: () => setSelectedPlan(plan),
      })),
      ...completedPlans.map((plan) => ({
        key: `dp-${plan.external_id}`,
        label: plan.completed_activity_name || plan.title || 'Done',
        kind: 'done',
        onClick: () => {
          if (plan.completed_activity_id) navigate(`/activities/${plan.completed_activity_id}`)
          else setSelectedPlan(plan)
        },
      })),
      ...unmatchedActivities.map((activity) => ({
        key: `a-${activity.id}`,
        label: activity.name,
        kind: 'done',
        to: `/activities/${activity.id}`,
      })),
    ]

    return (
      <div
        key={isoDate}
        className={`min-h-24 rounded-xl border p-2 ${
          isToday ? 'border-sage bg-sage/10' : 'border-[var(--aal-line)] bg-[var(--aal-card)]'
        } ${inMonth ? '' : 'opacity-40'}`}
      >
        <p className="mb-1 text-xs font-semibold text-[var(--aal-muted)]">
          {Number(isoDate.slice(8, 10))}
        </p>
        <div className="space-y-1">
          {chips.slice(0, 4).map((chip) =>
            chip.to ? (
              <Link
                key={chip.key}
                to={chip.to}
                className="block truncate rounded bg-sage/15 px-1.5 py-0.5 text-[10px] font-medium text-sage"
              >
                {chip.label}
              </Link>
            ) : (
              <button
                key={chip.key}
                type="button"
                onClick={chip.onClick}
                className={`block w-full truncate rounded px-1.5 py-0.5 text-left text-[10px] font-medium ${
                  chip.kind === 'planned'
                    ? 'bg-amber-status/15 text-amber-status'
                    : 'bg-sage/15 text-sage'
                }`}
              >
                {chip.label}
              </button>
            ),
          )}
          {chips.length > 4 && (
            <p className="text-[10px] text-[var(--aal-muted)]">+{chips.length - 4} more</p>
          )}
        </div>
      </div>
    )
  }

  return (
    <AppShell title="Schedule" flush>
      <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
        <div className="z-20 shrink-0 border-b border-[var(--aal-line)] bg-[var(--aal-bg)] px-4 pb-4 pt-4 sm:px-6 lg:px-8">
          <PageHeader
            eyebrow="Training"
            title="Schedule"
            subtitle="COROS plans and completed sessions — scroll the timeline or switch to calendar."
            actions={
              <div className="flex flex-wrap items-center gap-2">
                <div className="inline-flex rounded-xl border border-[var(--aal-line)] p-1">
                  <button
                    type="button"
                    onClick={() => setMode('timeline')}
                    className={`inline-flex items-center gap-1 rounded-lg px-3 py-1.5 text-sm ${
                      mode === 'timeline'
                        ? 'bg-sage/15 font-semibold text-sage'
                        : 'text-[var(--aal-muted)]'
                    }`}
                  >
                    <List className="h-4 w-4" /> Timeline
                  </button>
                  <button
                    type="button"
                    onClick={() => setMode('calendar')}
                    className={`inline-flex items-center gap-1 rounded-lg px-3 py-1.5 text-sm ${
                      mode === 'calendar'
                        ? 'bg-sage/15 font-semibold text-sage'
                        : 'text-[var(--aal-muted)]'
                    }`}
                  >
                    <CalendarDays className="h-4 w-4" /> Calendar
                  </button>
                </div>
                {connected && (
                  <button
                    type="button"
                    onClick={handleSync}
                    disabled={syncing}
                    className="inline-flex items-center gap-2 rounded-xl bg-sage px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-60"
                  >
                    <RefreshCw className={`h-4 w-4 ${syncing ? 'sync-spin' : ''}`} />
                    {syncing ? 'Syncing…' : 'Sync COROS'}
                  </button>
                )}
              </div>
            }
          />
          {error && <p className="mt-2 text-sm text-danger-muted">{error}</p>}
        </div>

        <div ref={scrollRef} className="min-h-0 flex-1 overflow-y-auto px-4 py-4 sm:px-6 lg:px-8">
          {loading ? (
            <LoadingDots label="Loading schedule…" />
          ) : !connected && plans.length === 0 && activities.length === 0 ? (
            <EmptyState
              title="Nothing scheduled yet"
              description="Connect COROS to pull planned workouts, or sync activities to fill completed sessions."
              actionLabel="Connect COROS"
              actionTo="/connect-coros"
            />
          ) : mode === 'timeline' ? (
            <div className="w-full space-y-3 pb-10">
              <p className="mb-3 text-sm text-[var(--aal-muted)]">
                Scroll up for past · today opens here · scroll down for future
              </p>
              {timelineDays.map((isoDate) => (
                <DaySection
                  key={isoDate}
                  isoDate={isoDate}
                  today={today}
                  plans={plansByDate.get(isoDate) || []}
                  activities={activitiesByDate.get(isoDate) || []}
                  onPlanClick={setSelectedPlan}
                  navigate={navigate}
                />
              ))}
            </div>
          ) : (
            <div className="w-full space-y-4 pb-10">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="inline-flex rounded-xl border border-[var(--aal-line)] p-1">
                  <button
                    type="button"
                    onClick={() => setCalMode('month')}
                    className={`rounded-lg px-3 py-1.5 text-sm ${
                      calMode === 'month'
                        ? 'bg-sage/15 font-semibold text-sage'
                        : 'text-[var(--aal-muted)]'
                    }`}
                  >
                    Month
                  </button>
                  <button
                    type="button"
                    onClick={() => setCalMode('week')}
                    className={`rounded-lg px-3 py-1.5 text-sm ${
                      calMode === 'week'
                        ? 'bg-sage/15 font-semibold text-sage'
                        : 'text-[var(--aal-muted)]'
                    }`}
                  >
                    Week
                  </button>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    className="rounded-lg border border-[var(--aal-line)] p-2"
                    onClick={() => {
                      if (calMode === 'month') {
                        const d = new Date(anchorMonth.year, anchorMonth.month - 1, 1)
                        setAnchorMonth({ year: d.getFullYear(), month: d.getMonth() })
                      } else {
                        setWeekStart(addDaysISO(weekStart, -7))
                      }
                    }}
                  >
                    <ChevronLeft className="h-4 w-4" />
                  </button>
                  <p className="min-w-40 text-center text-sm font-semibold">
                    {calMode === 'month'
                      ? new Date(anchorMonth.year, anchorMonth.month, 1).toLocaleDateString(
                          undefined,
                          { month: 'long', year: 'numeric' },
                        )
                      : `Week of ${weekStart}`}
                  </p>
                  <button
                    type="button"
                    className="rounded-lg border border-[var(--aal-line)] p-2"
                    onClick={() => {
                      if (calMode === 'month') {
                        const d = new Date(anchorMonth.year, anchorMonth.month + 1, 1)
                        setAnchorMonth({ year: d.getFullYear(), month: d.getMonth() })
                      } else {
                        setWeekStart(addDaysISO(weekStart, 7))
                      }
                    }}
                  >
                    <ChevronRight className="h-4 w-4" />
                  </button>
                </div>
              </div>

              <div className="grid grid-cols-7 gap-2 text-center text-[10px] font-semibold uppercase tracking-wide text-[var(--aal-muted)]">
                {['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'].map((d) => (
                  <div key={d}>{d}</div>
                ))}
              </div>

              {calMode === 'month' ? (
                <div className="space-y-2">
                  {monthWeeks.map((week) => (
                    <div key={week[0]} className="grid grid-cols-7 gap-2">
                      {week.map((isoDate) => renderCalendarCell(isoDate))}
                    </div>
                  ))}
                </div>
              ) : (
                <div className="grid grid-cols-7 gap-2">
                  {weekDays.map((isoDate) => renderCalendarCell(isoDate))}
                </div>
              )}

              <div className="flex gap-4 text-xs text-[var(--aal-muted)]">
                <span className="inline-flex items-center gap-1">
                  <span className="h-2 w-2 rounded-full bg-amber-status" /> Planned
                </span>
                <span className="inline-flex items-center gap-1">
                  <span className="h-2 w-2 rounded-full bg-sage" /> Completed
                </span>
              </div>
            </div>
          )}
        </div>
      </div>

      <PlanDetailModal
        plan={selectedPlan}
        onClose={() => setSelectedPlan(null)}
        navigate={navigate}
      />
    </AppShell>
  )
}
