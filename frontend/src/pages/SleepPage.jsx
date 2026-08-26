import { useEffect, useId, useMemo, useState } from 'react'
import { motion } from 'framer-motion'
import { ChevronLeft, ChevronRight, Moon, X } from 'lucide-react'
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { backfillMetricHistory, getMetricSeries } from '../api/coros'
import BarActiveGlow from '../components/charts/BarActiveEffects'
import AppShell from '../components/layout/AppShell'
import EmptyState from '../components/ui/EmptyState'
import LoadingDots from '../components/ui/LoadingDots'
import PageHeader from '../components/ui/PageHeader'
import RangeTabs from '../components/ui/RangeTabs'
import SectionCard from '../components/ui/SectionCard'
import { SLEEP_FACTOR_GUIDES } from '../utils/sleepGuides'
import {
  SLEEP_RANGES,
  STAGE_COLORS,
  aggregateByWeek,
  average,
  bedtimeConsistency,
  enrichSleepPoints,
  formatClock,
  formatDayLabel,
  formatMinutes,
  formatNumber,
  formatPct,
  periodTitle,
  previousNights,
  slicePointsForView,
  summarizePeriod,
} from '../utils/sleepHelpers'

function ScoreRing({ score, label = 'Score' }) {
  const value =
    score == null || Number.isNaN(Number(score))
      ? null
      : Math.max(0, Math.min(100, Number(score)))
  const radius = 54
  const circumference = 2 * Math.PI * radius
  const offset = value == null ? circumference : circumference * (1 - value / 100)

  return (
    <div className="relative mx-auto h-36 w-36">
      <svg viewBox="0 0 128 128" className="h-full w-full -rotate-90">
        <circle cx="64" cy="64" r={radius} fill="none" stroke="var(--aal-line)" strokeWidth="10" />
        <circle
          cx="64"
          cy="64"
          r={radius}
          fill="none"
          stroke="#6b9080"
          strokeWidth="10"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          className="transition-[stroke-dashoffset] duration-700 ease-out"
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-sage">{label}</p>
        <p className="text-4xl font-bold tabular-nums text-[var(--aal-ink)]">
          {value == null ? '—' : Math.round(value)}
        </p>
      </div>
    </div>
  )
}

function StageBar({ stages, className = '' }) {
  const parts = [
    { key: 'awake', label: 'Awake', value: stages?.awakeMin, color: STAGE_COLORS.awake },
    { key: 'rem', label: 'REM', value: stages?.remMin, color: STAGE_COLORS.rem },
    { key: 'light', label: 'Light', value: stages?.lightMin, color: STAGE_COLORS.light },
    { key: 'deep', label: 'Deep', value: stages?.deepMin, color: STAGE_COLORS.deep },
  ].filter((part) => part.value != null && part.value > 0)
  const total = parts.reduce((sum, part) => sum + part.value, 0)

  if (!total) {
    return (
      <div
        className={`rounded-full bg-[var(--aal-accent-soft)] px-3 py-3 text-sm text-[var(--aal-muted)] ${className}`}
      >
        Stage mix unavailable
      </div>
    )
  }

  return (
    <div className={className}>
      <div className="flex h-3 overflow-hidden rounded-full bg-[var(--aal-accent-soft)]">
        {parts.map((part) => (
          <div
            key={part.key}
            title={`${part.label}: ${formatMinutes(part.value)}`}
            style={{ width: `${(part.value / total) * 100}%`, backgroundColor: part.color }}
          />
        ))}
      </div>
      <div className="mt-3 flex flex-wrap gap-x-4 gap-y-2 text-xs text-[var(--aal-muted)]">
        {parts.map((part) => (
          <span key={part.key} className="inline-flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-full" style={{ backgroundColor: part.color }} />
            {part.label} {formatMinutes(part.value)}
          </span>
        ))}
      </div>
    </div>
  )
}

function FactorCard({ label, value, hint, onClick }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="rounded-2xl border border-[var(--aal-line)] bg-[var(--aal-card)] p-4 text-left transition hover:border-sage/40 hover:bg-sage/5 focus:outline-none focus-visible:ring-2 focus-visible:ring-sage/40"
    >
      <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-[var(--aal-muted)]">
        {label}
      </p>
      <p className="mt-2 text-2xl font-bold tabular-nums text-[var(--aal-ink)]">{value}</p>
      {hint ? <p className="mt-1 text-xs text-[var(--aal-muted)]">{hint}</p> : null}
      <p className="mt-3 text-xs font-semibold text-sage">Details →</p>
    </button>
  )
}

function SleepFactorModal({ factor, points, focus, view, onClose }) {
  const titleId = useId()
  const guide = SLEEP_FACTOR_GUIDES[factor]
  if (!factor || !guide) return null

  const chartKey = {
    score: 'score',
    duration: 'duration',
    deep: 'deep',
    rem: 'rem',
    light: 'light',
    awake: 'awake',
    hrv: 'hrv',
    sleepHr: 'sleepHr',
    consistency: 'bedtimeOffset',
  }[factor]

  const chartData = (points || []).map((point) => ({
    ...point,
    bedtimeOffset: bedtimeToChartOffset(point.bedtime),
  }))

  const focusValue = (() => {
    if (factor === 'score') return formatNumber(focus?.score ?? focus?.avgScore, 0)
    if (factor === 'duration') return formatMinutes(focus?.duration ?? focus?.avgDuration)
    if (factor === 'deep') return formatPct(focus?.deep ?? focus?.avgDeep)
    if (factor === 'rem') return formatPct(focus?.rem ?? focus?.avgRem)
    if (factor === 'light') return formatPct(focus?.light ?? focus?.avgLight)
    if (factor === 'awake') return formatMinutes(focus?.awake ?? focus?.avgAwake)
    if (factor === 'hrv') return formatNumber(focus?.hrv ?? focus?.avgHrv, 0, ' ms')
    if (factor === 'sleepHr') return formatNumber(focus?.sleepHr ?? focus?.avgSleepHr, 0, ' bpm')
    if (factor === 'consistency') {
      const c = focus?.consistency || bedtimeConsistency(points)
      return c.stdMinutes == null ? c.label : `±${Math.round(c.stdMinutes)}m`
    }
    return '—'
  })()

  const avgValue = (() => {
    if (factor === 'consistency') {
      const c = bedtimeConsistency(points)
      return c.avgBedtime ? `Avg bedtime ${formatClock(c.avgBedtime)}` : '—'
    }
    if (factor === 'duration' || factor === 'awake') {
      return `${view} avg ${formatMinutes(average(chartData.map((p) => p[chartKey])))}`
    }
    if (factor === 'deep' || factor === 'rem' || factor === 'light') {
      return `${view} avg ${formatPct(average(chartData.map((p) => p[chartKey])))}`
    }
    if (factor === 'hrv') {
      return `${view} avg ${formatNumber(average(chartData.map((p) => p.hrv)), 0, ' ms')}`
    }
    if (factor === 'sleepHr') {
      return `${view} avg ${formatNumber(average(chartData.map((p) => p.sleepHr)), 0, ' bpm')}`
    }
    return `${view} avg ${formatNumber(average(chartData.map((p) => p[chartKey])), 0)}`
  })()

  return (
    <div
      className="fixed inset-0 z-[80] flex items-end justify-center bg-black/45 p-4 sm:items-center"
      onClick={onClose}
      role="presentation"
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        className="max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-2xl border border-[var(--aal-line)] bg-[var(--aal-card)] p-6 shadow-xl"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="mb-4 flex items-start justify-between gap-3">
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-sage">
              {view} insight
            </p>
            <h2 id={titleId} className="mt-1 text-2xl font-bold text-[var(--aal-ink)]">
              {guide.title}
            </h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg border border-[var(--aal-line)] p-2 text-[var(--aal-muted)]"
            aria-label="Close"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="rounded-2xl bg-sage/10 px-4 py-4">
          <p className="text-3xl font-bold tabular-nums text-[var(--aal-ink)]">{focusValue}</p>
          <p className="mt-1 text-sm text-[var(--aal-muted)]">{avgValue}</p>
        </div>

        <div className="mt-5 h-48 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={chartData}>
              <CartesianGrid stroke="var(--aal-line)" strokeDasharray="3 3" />
              <XAxis dataKey="labelShort" tick={{ fontSize: 11 }} stroke="var(--aal-muted)" />
              <YAxis
                tick={{ fontSize: 11 }}
                stroke="var(--aal-muted)"
                domain={
                  factor === 'consistency' ? ['dataMin - 30', 'dataMax + 30'] : ['auto', 'auto']
                }
                tickFormatter={
                  factor === 'consistency'
                    ? (value) => clockFromOffset(value)
                    : undefined
                }
              />
              <Tooltip
                labelFormatter={(_, payload) => payload?.[0]?.payload?.date || _}
                formatter={(value) => {
                  if (value == null) return ['—', guide.title]
                  if (factor === 'duration' || factor === 'awake') {
                    return [formatMinutes(value), guide.title]
                  }
                  if (factor === 'deep' || factor === 'rem' || factor === 'light') {
                    return [formatPct(value), guide.title]
                  }
                  if (factor === 'hrv') return [formatNumber(value, 0, ' ms'), guide.title]
                  if (factor === 'sleepHr') return [formatNumber(value, 0, ' bpm'), guide.title]
                  if (factor === 'consistency') {
                    return [formatClock(clockFromOffset(value, true)), 'Bedtime']
                  }
                  return [formatNumber(value, 0), guide.title]
                }}
              />
              <Area
                type="monotone"
                dataKey={chartKey}
                stroke="#6b9080"
                fill="#6b908033"
                strokeWidth={2}
                connectNulls
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        <p className="mt-5 text-sm leading-relaxed text-[var(--aal-muted)]">{guide.summary}</p>
        <div className="mt-4 space-y-4">
          {guide.sections.map((section) => (
            <div key={section.heading}>
              <h3 className="text-sm font-semibold text-[var(--aal-ink)]">{section.heading}</h3>
              <p className="mt-1 text-sm leading-relaxed text-[var(--aal-muted)]">{section.body}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

function bedtimeToChartOffset(clock) {
  if (!clock) return null
  const match = String(clock).match(/(\d{1,2}):(\d{2})/)
  if (!match) return null
  let minutes = Number(match[1]) * 60 + Number(match[2])
  if (minutes < 18 * 60) minutes += 24 * 60
  return minutes
}

function clockFromOffset(value, asHHMM = false) {
  const mins = ((Math.round(value) % (24 * 60)) + 24 * 60) % (24 * 60)
  const h = Math.floor(mins / 60)
  const m = mins % 60
  const hhmm = `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}`
  return asHHMM ? hhmm : `${h}:${m.toString().padStart(2, '0')}`
}

function StagePie({ stages }) {
  const stagePie = [
    { name: 'Awake', value: stages?.awakeMin, color: STAGE_COLORS.awake },
    { name: 'REM', value: stages?.remMin, color: STAGE_COLORS.rem },
    { name: 'Light', value: stages?.lightMin, color: STAGE_COLORS.light },
    { name: 'Deep', value: stages?.deepMin, color: STAGE_COLORS.deep },
  ].filter((item) => item.value != null && item.value > 0)

  if (!stagePie.length) {
    return (
      <p className="flex h-52 items-center justify-center text-sm text-[var(--aal-muted)]">
        No stage mix for this period
      </p>
    )
  }

  return (
    <div className="grid gap-4 sm:grid-cols-2 sm:items-center">
      <div className="h-52">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={stagePie}
              dataKey="value"
              nameKey="name"
              innerRadius={48}
              outerRadius={78}
              paddingAngle={2}
            >
              {stagePie.map((entry) => (
                <Cell key={entry.name} fill={entry.color} />
              ))}
            </Pie>
            <Tooltip formatter={(value, name) => [formatMinutes(value), name]} />
          </PieChart>
        </ResponsiveContainer>
      </div>
      <div className="space-y-3">
        {stagePie.map((entry) => (
          <div
            key={entry.name}
            className="flex items-center justify-between rounded-xl border border-[var(--aal-line)] px-3 py-2"
          >
            <span className="inline-flex items-center gap-2 text-sm font-medium">
              <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: entry.color }} />
              {entry.name}
            </span>
            <span className="text-sm tabular-nums text-[var(--aal-muted)]">
              {formatMinutes(entry.value)}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}

export default function SleepPage() {
  const [view, setView] = useState('day')
  const [series, setSeries] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [backfilling, setBackfilling] = useState(false)
  const [activeFactor, setActiveFactor] = useState(null)
  /** Index from end of all nights — 0 = latest night (Day view navigation). */
  const [dayOffset, setDayOffset] = useState(0)

  // Load full available history once so Day/Week/Month/Year can slice instantly.
  useEffect(() => {
    let cancelled = false
    async function load() {
      setLoading(true)
      setError('')
      try {
        const data = await getMetricSeries('sleep', '1y')
        if (!cancelled) setSeries(data)
      } catch (err) {
        if (!cancelled) setError(err.message || 'Failed to load sleep data.')
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    load()
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    if (!activeFactor) return undefined
    function onKey(event) {
      if (event.key === 'Escape') setActiveFactor(null)
    }
    document.addEventListener('keydown', onKey)
    const previous = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', onKey)
      document.body.style.overflow = previous
    }
  }, [activeFactor])

  function handleViewChange(next) {
    setView(next)
    setDayOffset(0)
    setActiveFactor(null)
  }

  const allPoints = useMemo(() => enrichSleepPoints(series), [series])
  const allValued = useMemo(
    () => allPoints.filter((p) => p.score != null || p.duration != null),
    [allPoints],
  )

  const dayNight = useMemo(() => {
    if (!allValued.length) return null
    const index = Math.max(0, allValued.length - 1 - dayOffset)
    return allValued[index] || null
  }, [allValued, dayOffset])

  const viewPoints = useMemo(() => {
    if (view === 'day') return dayNight ? [dayNight] : []
    return slicePointsForView(allValued, view)
  }, [view, allValued, dayNight])

  const chartPoints = useMemo(() => {
    if (view === 'year') return aggregateByWeek(viewPoints)
    return viewPoints
  }, [view, viewPoints])

  const summary = useMemo(() => summarizePeriod(viewPoints), [viewPoints])

  const compareNights = useMemo(() => {
    if (view !== 'day' || !dayNight?.date) return []
    return [...previousNights(allValued, dayNight.date, 7), dayNight]
  }, [view, dayNight, allValued])

  const consistency =
    view === 'day'
      ? bedtimeConsistency(compareNights)
      : summary.consistency

  const heroScore = view === 'day' ? dayNight?.score : summary.avgScore
  const heroDuration = view === 'day' ? dayNight?.duration : summary.avgDuration
  const heroStages =
    view === 'day'
      ? dayNight
      : {
          deepMin: summary.deepMin,
          lightMin: summary.lightMin,
          remMin: summary.remMin,
          awakeMin: summary.awakeMin,
        }

  async function handleExploreHistory() {
    setBackfilling(true)
    setError('')
    try {
      const data = await backfillMetricHistory('sleep', '1y')
      setSeries(data)
    } catch (err) {
      setError(err.message || 'Failed to backfill sleep history.')
    } finally {
      setBackfilling(false)
    }
  }

  const canPrevDay = dayOffset < Math.max(0, allValued.length - 1)
  const canNextDay = dayOffset > 0

  const viewEyebrow = {
    day: 'Day insight',
    week: 'Week insight',
    month: 'Month insight',
    year: 'Year insight',
  }[view]

  const factorFocus = view === 'day' ? dayNight : summary
  const modalPoints = view === 'day' ? compareNights : chartPoints

  return (
    <AppShell title="Sleep">
      <PageHeader
        eyebrow="Health"
        title="Sleep"
        subtitle="Switch Day / Week / Month / Year for COROS-style sleep insights — averages, stages, and trends change with each view."
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <RangeTabs
              value={view}
              onChange={handleViewChange}
              options={SLEEP_RANGES.map(({ id, label }) => ({ id, label }))}
            />
            <button
              type="button"
              onClick={handleExploreHistory}
              disabled={backfilling || loading}
              className="rounded-xl border border-[var(--aal-line)] px-3 py-2 text-sm font-medium disabled:opacity-60"
            >
              {backfilling ? 'Loading history…' : 'Explore history'}
            </button>
          </div>
        }
      />

      {error ? <p className="mb-4 text-sm text-danger-muted">{error}</p> : null}

      {loading ? (
        <SectionCard>
          <LoadingDots label="Loading sleep…" />
        </SectionCard>
      ) : !allValued.length ? (
        <EmptyState
          title="No sleep data yet"
          description="Connect COROS and sync to pull sleep score, stages, and HRV."
          actionLabel="Connect COROS"
          actionTo="/connect-coros"
        />
      ) : (
        <motion.div
          key={view}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.28 }}
          className="space-y-6"
        >
          <div className="overflow-hidden rounded-3xl border border-[var(--aal-line)] bg-[linear-gradient(160deg,var(--aal-card)_0%,var(--aal-accent-soft)_100%)] p-5 sm:p-7">
            <div className="flex flex-col gap-6 lg:flex-row lg:items-center lg:justify-between">
              <div className="flex items-start gap-4">
                <div className="rounded-2xl bg-sage/15 p-3 text-sage">
                  <Moon className="h-6 w-6" />
                </div>
                <div>
                  <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-sage">
                    {viewEyebrow}
                  </p>
                  <div className="mt-1 flex items-center gap-2">
                    {view === 'day' ? (
                      <>
                        <button
                          type="button"
                          disabled={!canPrevDay}
                          onClick={() => setDayOffset((v) => v + 1)}
                          className="rounded-lg border border-[var(--aal-line)] p-1.5 disabled:opacity-40"
                          aria-label="Previous night"
                        >
                          <ChevronLeft className="h-4 w-4" />
                        </button>
                        <h2 className="text-2xl font-bold text-[var(--aal-ink)]">
                          {periodTitle(view, summary, dayNight)}
                        </h2>
                        <button
                          type="button"
                          disabled={!canNextDay}
                          onClick={() => setDayOffset((v) => Math.max(0, v - 1))}
                          className="rounded-lg border border-[var(--aal-line)] p-1.5 disabled:opacity-40"
                          aria-label="Next night"
                        >
                          <ChevronRight className="h-4 w-4" />
                        </button>
                      </>
                    ) : (
                      <h2 className="text-2xl font-bold text-[var(--aal-ink)]">
                        {periodTitle(view, summary, dayNight)}
                      </h2>
                    )}
                  </div>
                  <p className="mt-1 text-sm text-[var(--aal-muted)]">
                    {view === 'day' ? (
                      <>
                        {formatClock(dayNight?.bedtime)} → {formatClock(dayNight?.wake)}
                        {dayNight?.nap != null ? ` · Nap ${formatMinutes(dayNight.nap)}` : ''}
                      </>
                    ) : (
                      <>
                        {summary.nights} night{summary.nights === 1 ? '' : 's'} · avg score{' '}
                        {formatNumber(summary.avgScore, 0)} · avg sleep{' '}
                        {formatMinutes(summary.avgDuration)}
                      </>
                    )}
                  </p>
                </div>
              </div>

              <div className="grid flex-1 gap-6 sm:grid-cols-[auto_1fr] sm:items-center">
                <button
                  type="button"
                  onClick={() => setActiveFactor('score')}
                  className="justify-self-center"
                >
                  <ScoreRing
                    score={heroScore}
                    label={view === 'day' ? 'Score' : 'Avg score'}
                  />
                </button>
                <div className="space-y-4">
                  <button
                    type="button"
                    onClick={() => setActiveFactor('duration')}
                    className="text-left"
                  >
                    <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-[var(--aal-muted)]">
                      {view === 'day' ? 'Total sleep' : `Avg sleep / night`}
                    </p>
                    <p className="text-4xl font-bold tabular-nums text-[var(--aal-ink)]">
                      {formatMinutes(heroDuration)}
                    </p>
                  </button>
                  <StageBar stages={heroStages} />
                </div>
              </div>
            </div>
          </div>

          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <FactorCard
              label={view === 'day' ? 'Deep sleep' : 'Avg deep'}
              value={formatPct(view === 'day' ? dayNight?.deep : summary.avgDeep)}
              hint={view === 'day' ? 'Share of this night' : `${view} average`}
              onClick={() => setActiveFactor('deep')}
            />
            <FactorCard
              label={view === 'day' ? 'REM sleep' : 'Avg REM'}
              value={formatPct(view === 'day' ? dayNight?.rem : summary.avgRem)}
              hint={view === 'day' ? 'Share of this night' : `${view} average`}
              onClick={() => setActiveFactor('rem')}
            />
            <FactorCard
              label={view === 'day' ? 'Awake' : 'Avg awake'}
              value={formatMinutes(view === 'day' ? dayNight?.awake : summary.avgAwake)}
              hint={view === 'day' ? 'Wakefulness overnight' : `${view} average`}
              onClick={() => setActiveFactor('awake')}
            />
            <FactorCard
              label="Bedtime consistency"
              value={
                consistency.stdMinutes == null
                  ? consistency.label
                  : `±${Math.round(consistency.stdMinutes)}m`
              }
              hint={
                consistency.avgBedtime
                  ? `Avg ${formatClock(consistency.avgBedtime)} · ${consistency.label}`
                  : consistency.label
              }
              onClick={() => setActiveFactor('consistency')}
            />
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            <SectionCard
              title={view === 'day' ? 'Sleep stages' : `${view} stage mix`}
              subtitle={
                view === 'day'
                  ? 'Composition for the selected night.'
                  : `Average stage minutes across ${summary.nights} night${summary.nights === 1 ? '' : 's'}.`
              }
            >
              <StagePie stages={heroStages} />
              {view !== 'day' ? (
                <div className="mt-4 grid grid-cols-3 gap-2 text-center text-xs">
                  <div className="rounded-xl bg-[var(--aal-accent-soft)] px-2 py-3">
                    <p className="text-[var(--aal-muted)]">Deep</p>
                    <p className="mt-1 font-semibold tabular-nums">{formatPct(summary.avgDeep)}</p>
                  </div>
                  <div className="rounded-xl bg-[var(--aal-accent-soft)] px-2 py-3">
                    <p className="text-[var(--aal-muted)]">Light</p>
                    <p className="mt-1 font-semibold tabular-nums">{formatPct(summary.avgLight)}</p>
                  </div>
                  <div className="rounded-xl bg-[var(--aal-accent-soft)] px-2 py-3">
                    <p className="text-[var(--aal-muted)]">REM</p>
                    <p className="mt-1 font-semibold tabular-nums">{formatPct(summary.avgRem)}</p>
                  </div>
                </div>
              ) : null}
            </SectionCard>

            <SectionCard
              title="Recovery signals"
              subtitle={
                view === 'day'
                  ? 'Overnight HRV and sleep HR for this night.'
                  : `Average HRV and sleep HR for this ${view}.`
              }
            >
              <div className="grid gap-3 sm:grid-cols-2">
                <FactorCard
                  label={view === 'day' ? 'Sleep HRV' : 'Avg HRV'}
                  value={formatNumber(
                    view === 'day' ? dayNight?.hrv : summary.avgHrv,
                    0,
                    ' ms',
                  )}
                  hint={
                    view === 'day'
                      ? dayNight?.hrvAssessment || 'Overnight assessment'
                      : `${summary.nights} nights`
                  }
                  onClick={() => setActiveFactor('hrv')}
                />
                <FactorCard
                  label={view === 'day' ? 'Avg sleep HR' : 'Avg sleep HR'}
                  value={formatNumber(
                    view === 'day' ? dayNight?.sleepHr : summary.avgSleepHr,
                    0,
                    ' bpm',
                  )}
                  hint={view === 'day' ? 'This night' : `${view} average`}
                  onClick={() => setActiveFactor('sleepHr')}
                />
              </div>
              {view !== 'day' ? (
                <div className="mt-4 h-44">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={chartPoints}>
                      <CartesianGrid stroke="var(--aal-line)" strokeDasharray="3 3" />
                      <XAxis
                        dataKey="labelShort"
                        tick={{ fontSize: 11 }}
                        stroke="var(--aal-muted)"
                      />
                      <YAxis tick={{ fontSize: 11 }} stroke="var(--aal-muted)" />
                      <Tooltip
                        labelFormatter={(_, payload) => payload?.[0]?.payload?.date || _}
                      />
                      <Line
                        type="monotone"
                        dataKey="hrv"
                        name="HRV"
                        stroke="#6b9080"
                        strokeWidth={2.2}
                        dot={chartPoints.length <= 14}
                        connectNulls
                      />
                      <Line
                        type="monotone"
                        dataKey="sleepHr"
                        name="Sleep HR"
                        stroke="#6b9ac4"
                        strokeWidth={2}
                        dot={chartPoints.length <= 14}
                        connectNulls
                      />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              ) : null}
            </SectionCard>
          </div>

          {view === 'day' ? (
            <SectionCard
              title="Last 7 nights"
              subtitle="How this night compares to recent sleep — score and duration."
            >
              <div className="h-64 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={compareNights}>
                    <CartesianGrid stroke="var(--aal-line)" strokeDasharray="3 3" />
                    <XAxis
                      dataKey="date"
                      tick={{ fontSize: 11 }}
                      stroke="var(--aal-muted)"
                      tickFormatter={(value) => formatDayLabel(value, 'weekday')}
                    />
                    <YAxis tick={{ fontSize: 11 }} stroke="var(--aal-muted)" />
                    <Tooltip
                      cursor={{ fill: 'transparent' }}
                      labelFormatter={(value) => formatDayLabel(value, 'full')}
                      formatter={(value, name) => [
                        name === 'Duration' ? formatMinutes(value) : formatNumber(value, 0),
                        name,
                      ]}
                    />
                    <Bar
                      dataKey="score"
                      name="Score"
                      fill="#6b9080"
                      radius={[6, 6, 0, 0]}
                      activeBar={BarActiveGlow}
                    />
                    <Bar
                      dataKey="duration"
                      name="Duration"
                      fill="#6b9ac4"
                      radius={[6, 6, 0, 0]}
                      activeBar={BarActiveGlow}
                    />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </SectionCard>
          ) : (
            <>
              <SectionCard
                title={view === 'year' ? 'Weekly sleep trends' : `${view} sleep trends`}
                subtitle={
                  view === 'year'
                    ? 'Weekly averages across the year (from first collected sample).'
                    : `Daily score and duration for this ${view}.`
                }
              >
                <div className="h-72 w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={chartPoints}>
                      <CartesianGrid stroke="var(--aal-line)" strokeDasharray="3 3" />
                      <XAxis
                        dataKey="labelShort"
                        tick={{ fontSize: 11 }}
                        stroke="var(--aal-muted)"
                      />
                      <YAxis yAxisId="left" tick={{ fontSize: 11 }} stroke="var(--aal-muted)" />
                      <YAxis
                        yAxisId="right"
                        orientation="right"
                        tick={{ fontSize: 11 }}
                        stroke="var(--aal-muted)"
                      />
                      <Tooltip
                        labelFormatter={(_, payload) => payload?.[0]?.payload?.date || _}
                        formatter={(value, name) => [
                          name === 'Duration' ? formatMinutes(value) : formatNumber(value, 0),
                          name,
                        ]}
                      />
                      <Line
                        yAxisId="left"
                        type="monotone"
                        dataKey="score"
                        name="Score"
                        stroke="#6b9080"
                        strokeWidth={2.5}
                        dot={chartPoints.length <= 16}
                        connectNulls
                      />
                      <Line
                        yAxisId="right"
                        type="monotone"
                        dataKey="duration"
                        name="Duration"
                        stroke="#6b9ac4"
                        strokeWidth={2}
                        dot={chartPoints.length <= 16}
                        connectNulls
                      />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </SectionCard>

              <SectionCard
                title={view === 'year' ? 'Weekly stage mix' : `${view} stage mix over time`}
                subtitle="Stacked minutes — Deep, Light, REM, and Awake."
              >
                <div className="h-72 w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={chartPoints}>
                      <CartesianGrid stroke="var(--aal-line)" strokeDasharray="3 3" />
                      <XAxis
                        dataKey="labelShort"
                        tick={{ fontSize: 11 }}
                        stroke="var(--aal-muted)"
                      />
                      <YAxis tick={{ fontSize: 11 }} stroke="var(--aal-muted)" />
                      <Tooltip
                        cursor={{ fill: 'transparent' }}
                        labelFormatter={(_, payload) => payload?.[0]?.payload?.date || _}
                        formatter={(value, name) => [formatMinutes(value), name]}
                      />
                      <Bar dataKey="deepMin" name="Deep" stackId="stages" fill={STAGE_COLORS.deep} />
                      <Bar
                        dataKey="lightMin"
                        name="Light"
                        stackId="stages"
                        fill={STAGE_COLORS.light}
                      />
                      <Bar dataKey="remMin" name="REM" stackId="stages" fill={STAGE_COLORS.rem} />
                      <Bar
                        dataKey="awakeMin"
                        name="Awake"
                        stackId="stages"
                        fill={STAGE_COLORS.awake}
                      />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </SectionCard>
            </>
          )}

          {view !== 'day' ? (
            <SectionCard title={`${view} snapshot`} subtitle="Quick totals for the selected window.">
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                <div className="rounded-xl border border-[var(--aal-line)] px-4 py-3">
                  <p className="text-xs text-[var(--aal-muted)]">Nights tracked</p>
                  <p className="mt-1 text-2xl font-bold tabular-nums">{summary.nights}</p>
                </div>
                <div className="rounded-xl border border-[var(--aal-line)] px-4 py-3">
                  <p className="text-xs text-[var(--aal-muted)]">Total sleep</p>
                  <p className="mt-1 text-2xl font-bold tabular-nums">
                    {formatMinutes(summary.totalSleep)}
                  </p>
                </div>
                <div className="rounded-xl border border-[var(--aal-line)] px-4 py-3">
                  <p className="text-xs text-[var(--aal-muted)]">Avg bedtime</p>
                  <p className="mt-1 text-2xl font-bold tabular-nums">
                    {formatClock(summary.consistency?.avgBedtime)}
                  </p>
                </div>
                <div className="rounded-xl border border-[var(--aal-line)] px-4 py-3">
                  <p className="text-xs text-[var(--aal-muted)]">Consistency</p>
                  <p className="mt-1 text-2xl font-bold tabular-nums">
                    {summary.consistency?.stdMinutes == null
                      ? summary.consistency?.label || '—'
                      : `±${Math.round(summary.consistency.stdMinutes)}m`}
                  </p>
                </div>
              </div>
            </SectionCard>
          ) : null}
        </motion.div>
      )}

      <SleepFactorModal
        factor={activeFactor}
        points={modalPoints}
        focus={factorFocus}
        view={view}
        onClose={() => setActiveFactor(null)}
      />
    </AppShell>
  )
}
