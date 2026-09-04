import { useEffect, useId, useMemo, useState } from 'react'
import { motion } from 'framer-motion'
import { ChevronLeft, ChevronRight, Info, Moon, X } from 'lucide-react'
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
import SleepBarActive from '../components/charts/SleepBarActive'
import AppShell from '../components/layout/AppShell'
import EmptyState from '../components/ui/EmptyState'
import LoadingDots from '../components/ui/LoadingDots'
import PageHeader from '../components/ui/PageHeader'
import RangeTabs from '../components/ui/RangeTabs'
import SectionCard from '../components/ui/SectionCard'
import { SLEEP_FACTOR_GUIDES } from '../utils/sleepGuides'
import {
  SLEEP_CHART,
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

/* Sleep score ring parked — re-enable with SLEEP_SCORE_ENABLED when MCP matches COROS app.
function ScoreRing({ score, label = 'Score', hint = null }) { ... }
*/

function SleepTooltip({ active, payload, label, labelFormatter, valueFormatter }) {
  if (!active || !payload?.length) return null
  const title = labelFormatter ? labelFormatter(label, payload) : label
  return (
    <div
      className="rounded-xl border px-3 py-2.5 shadow-lg backdrop-blur-sm"
      style={{
        background: 'color-mix(in srgb, var(--aal-card) 92%, transparent)',
        borderColor: 'var(--aal-line)',
      }}
    >
      <p className="text-[11px] font-semibold text-[var(--aal-muted)]">{title}</p>
      <div className="mt-1.5 space-y-1">
        {payload.map((entry) => {
          const formatted = valueFormatter
            ? valueFormatter(entry.value, entry.name, entry)
            : [entry.value, entry.name]
          const [val, name] = Array.isArray(formatted) ? formatted : [formatted, entry.name]
          return (
            <div key={entry.dataKey || entry.name} className="flex items-center gap-2 text-xs">
              <span
                className="size-2 shrink-0 rounded-full"
                style={{ background: entry.color || entry.fill || SLEEP_CHART.duration }}
              />
              <span className="text-[var(--aal-muted)]">{name}</span>
              <span className="ml-auto font-semibold tabular-nums text-[var(--aal-ink)]">{val}</span>
            </div>
          )
        })}
      </div>
    </div>
  )
}

function StageBar({ stages, className = '', compact = false }) {
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
        className={`rounded-full bg-[var(--aal-accent-soft)] px-3 py-2 text-xs text-[var(--aal-muted)] ${className}`}
      >
        Stage mix unavailable
      </div>
    )
  }

  return (
    <div className={className}>
      <div
        className={`flex overflow-hidden rounded-full bg-slate-900/10 dark:bg-white/10 ${
          compact ? 'h-3' : 'h-3.5'
        }`}
      >
        {parts.map((part) => (
          <div
            key={part.key}
            title={`${part.label}: ${formatMinutes(part.value)}`}
            className="transition-[width] duration-500 first:rounded-l-full last:rounded-r-full"
            style={{ width: `${(part.value / total) * 100}%`, backgroundColor: part.color }}
          />
        ))}
      </div>
      <div
        className={`flex flex-wrap text-[var(--aal-muted)] ${
          compact ? 'mt-2 gap-x-4 gap-y-1.5 text-sm' : 'mt-3 gap-x-4 gap-y-2 text-sm'
        }`}
      >
        {parts.map((part) => (
          <span key={part.key} className="inline-flex items-center gap-1.5">
            <span
              className={`rounded-full ${compact ? 'h-2 w-2' : 'h-2.5 w-2.5'}`}
              style={{ backgroundColor: part.color }}
            />
            {part.label}{' '}
            <span className="font-semibold tabular-nums text-[var(--aal-ink)]">
              {formatMinutes(part.value)}
            </span>
          </span>
        ))}
      </div>
    </div>
  )
}

function FactorCard({
  label,
  value,
  hint,
  onClick,
  onInfoClick = null,
  infoLabel = 'About this metric',
  accent = SLEEP_CHART.duration,
}) {
  return (
    <div
      className="group relative overflow-hidden rounded-2xl border border-[var(--aal-line)] bg-[var(--aal-card)] p-4 transition duration-200 hover:-translate-y-0.5 hover:shadow-[0_12px_28px_-16px_rgba(55,48,163,0.45)]"
      style={{ boxShadow: 'inset 3px 0 0 0 ' + accent }}
    >
      <div className="flex items-start justify-between gap-2">
        <button
          type="button"
          onClick={onClick}
          className="min-w-0 flex-1 text-left focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-400/40"
        >
          <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-[var(--aal-muted)]">
            {label}
          </p>
          <p className="mt-2 text-2xl font-bold tabular-nums text-[var(--aal-ink)] transition group-hover:text-indigo-600 dark:group-hover:text-indigo-300">
            {value}
          </p>
          {hint ? <p className="mt-1 text-xs text-[var(--aal-muted)]">{hint}</p> : null}
          <p className="mt-3 text-xs font-semibold text-indigo-500 opacity-80 transition group-hover:opacity-100">
            Details →
          </p>
        </button>
        {onInfoClick ? (
          <button
            type="button"
            onClick={(event) => {
              event.stopPropagation()
              onInfoClick()
            }}
            className="shrink-0 rounded-full border border-[var(--aal-line)] p-1.5 text-[var(--aal-muted)] transition hover:border-indigo-300 hover:bg-indigo-50 hover:text-indigo-600 dark:hover:bg-indigo-950/40 dark:hover:text-indigo-300"
            aria-label={infoLabel}
            title={infoLabel}
          >
            <Info className="h-3.5 w-3.5" />
          </button>
        ) : null}
      </div>
    </div>
  )
}

function SleepFactorModal({ factor, points, focus, view, onClose }) {
  const titleId = useId()
  const guide = SLEEP_FACTOR_GUIDES[factor]
  if (!factor || !guide) return null

  const chartKey = {
    score: 'score',
    duration: 'duration',
    nap: 'nap',
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
    if (factor === 'nap') return formatMinutes(focus?.nap ?? focus?.avgNap)
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
    if (factor === 'duration' || factor === 'awake' || factor === 'nap') {
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
            <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-indigo-500 dark:text-indigo-300">
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

        <div className="rounded-2xl bg-indigo-500/10 px-4 py-4">
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
                  if (factor === 'duration' || factor === 'awake' || factor === 'nap') {
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
                stroke={SLEEP_CHART.duration}
                fill={SLEEP_CHART.durationSoft}
                strokeWidth={2.4}
                connectNulls
                activeDot={{ r: 5, strokeWidth: 2, stroke: '#fff' }}
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
  const total = stagePie.reduce((sum, item) => sum + item.value, 0)

  if (!stagePie.length) {
    return (
      <p className="flex h-52 items-center justify-center text-sm text-[var(--aal-muted)]">
        No stage mix for this period
      </p>
    )
  }

  return (
    <div className="grid gap-4 sm:grid-cols-2 sm:items-center">
      <div className="relative h-56">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={stagePie}
              dataKey="value"
              nameKey="name"
              innerRadius={58}
              outerRadius={86}
              paddingAngle={3}
              stroke="var(--aal-card)"
              strokeWidth={3}
            >
              {stagePie.map((entry) => (
                <Cell
                  key={entry.name}
                  fill={entry.color}
                  className="origin-center transition duration-200 hover:opacity-90"
                />
              ))}
            </Pie>
            <Tooltip
              content={
                <SleepTooltip valueFormatter={(value, name) => [formatMinutes(value), name]} />
              }
            />
          </PieChart>
        </ResponsiveContainer>
        <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
          <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[var(--aal-muted)]">
            Asleep
          </p>
          <p className="text-lg font-bold tabular-nums text-[var(--aal-ink)]">
            {formatMinutes(total - (stages?.awakeMin || 0))}
          </p>
        </div>
      </div>
      <div className="space-y-2.5">
        {stagePie.map((entry) => (
          <div
            key={entry.name}
            className="flex items-center justify-between rounded-xl border border-[var(--aal-line)] bg-[var(--aal-card)] px-3 py-2.5 transition hover:border-indigo-300/50 hover:bg-indigo-50/40 dark:hover:bg-indigo-950/30"
          >
            <span className="inline-flex items-center gap-2 text-sm font-medium text-[var(--aal-ink)]">
              <span
                className="h-2.5 w-2.5 rounded-full shadow-[0_0_0_3px_rgba(0,0,0,0.04)]"
                style={{ backgroundColor: entry.color }}
              />
              {entry.name}
            </span>
            <span className="text-sm font-semibold tabular-nums text-[var(--aal-ink)]">
              {formatMinutes(entry.value)}
              <span className="ml-1.5 text-[11px] font-normal text-[var(--aal-muted)]">
                {total ? `${Math.round((entry.value / total) * 100)}%` : ''}
              </span>
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
        subtitle="Overnight stages, naps, and recovery signals from COROS — Day / Week / Month / Year."
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
              className="rounded-xl border border-[var(--aal-line)] bg-[var(--aal-card)] px-3 py-2 text-sm font-medium transition hover:border-indigo-300 hover:text-indigo-600 disabled:opacity-60 dark:hover:text-indigo-300"
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
          description="Connect COROS and sync to pull sleep duration, stages, naps, and HRV."
          actionLabel="Connect COROS"
          actionTo="/connect-coros"
        />
      ) : (
        <motion.div
          key={view}
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.32, ease: [0.22, 1, 0.36, 1] }}
          className="space-y-6"
        >
          <div className="relative overflow-hidden rounded-2xl border border-[var(--aal-line)] px-4 py-3.5 sm:px-5 sm:py-4">
            <div
              className="pointer-events-none absolute inset-0"
              style={{
                background:
                  'radial-gradient(120% 80% at 0% 0%, rgba(55,48,163,0.14), transparent 55%), radial-gradient(90% 70% at 100% 20%, rgba(56,189,248,0.1), transparent 50%), linear-gradient(165deg, var(--aal-card), color-mix(in srgb, #312e81 6%, var(--aal-card)))',
              }}
            />
            <div className="relative flex flex-col gap-3 lg:flex-row lg:items-center lg:gap-4">
              <div className="flex shrink-0 items-center gap-3">
                <div className="shrink-0 rounded-xl bg-indigo-600/15 p-2 text-indigo-600 dark:text-indigo-300">
                  <Moon className="h-[18px] w-[18px]" />
                </div>
                <div className="min-w-0">
                  <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-indigo-500 dark:text-indigo-300">
                    {viewEyebrow}
                  </p>
                  <div className="mt-0.5 flex flex-nowrap items-center gap-1.5">
                    {view === 'day' ? (
                      <>
                        <button
                          type="button"
                          disabled={!canPrevDay}
                          onClick={() => setDayOffset((v) => v + 1)}
                          className="shrink-0 rounded-md border border-[var(--aal-line)] bg-[var(--aal-card)]/80 p-1 transition hover:border-indigo-300 disabled:opacity-40"
                          aria-label="Previous night"
                        >
                          <ChevronLeft className="h-3.5 w-3.5" />
                        </button>
                        <h2 className="whitespace-nowrap text-lg font-bold leading-tight text-[var(--aal-ink)] sm:text-xl">
                          {periodTitle(view, summary, dayNight)}
                        </h2>
                        <button
                          type="button"
                          disabled={!canNextDay}
                          onClick={() => setDayOffset((v) => Math.max(0, v - 1))}
                          className="shrink-0 rounded-md border border-[var(--aal-line)] bg-[var(--aal-card)]/80 p-1 transition hover:border-indigo-300 disabled:opacity-40"
                          aria-label="Next night"
                        >
                          <ChevronRight className="h-3.5 w-3.5" />
                        </button>
                      </>
                    ) : (
                      <h2 className="whitespace-nowrap text-lg font-bold leading-tight text-[var(--aal-ink)] sm:text-xl">
                        {periodTitle(view, summary, dayNight)}
                      </h2>
                    )}
                  </div>
                  <p className="mt-0.5 text-xs text-[var(--aal-muted)] sm:text-sm">
                    {view === 'day' ? (
                      <>
                        {formatClock(dayNight?.bedtime)} → {formatClock(dayNight?.wake)}
                        {dayNight?.mainSleep != null
                          ? ``
                          : ''}
                        {dayNight?.nap != null
                          ? ``
                          : ''}
                      </>
                    ) : (
                      <>
                        {summary.nights} night{summary.nights === 1 ? '' : 's'} · avg sleep{' '}
                        {formatMinutes(summary.avgDuration)}
                      </>
                    )}
                  </p>
                </div>
              </div>

              <button
                type="button"
                onClick={() => setActiveFactor('duration')}
                className="shrink-0 rounded-xl border border-indigo-500/20 bg-[var(--aal-card)]/80 px-5 py-3 text-left backdrop-blur-sm transition hover:border-indigo-400/50 hover:shadow-[0_10px_28px_-18px_rgba(55,48,163,0.55)] lg:min-w-[11.5rem] xl:min-w-[13rem]"
              >
                <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-indigo-500 dark:text-indigo-300">
                  {view === 'day' ? 'Total sleep' : 'Avg / night'}
                </p>
                <p className="mt-1 text-3xl font-bold tabular-nums tracking-tight text-[var(--aal-ink)] xl:text-4xl">
                  {formatMinutes(heroDuration)}
                </p>
                {view === 'day' && (dayNight?.mainSleep != null || dayNight?.nap != null) ? (
                  <p className="mt-1 text-xs text-[var(--aal-muted)]">
                    {dayNight?.mainSleep != null
                      ? `Main ${formatMinutes(dayNight.mainSleep)}`
                      : 'Main —'}
                    {dayNight?.nap != null ? ` + Nap ${formatMinutes(dayNight.nap)}` : ''}
                  </p>
                ) : null}
              </button>

              <div className="min-w-0 flex-1">
                <StageBar stages={heroStages} compact />
              </div>
            </div>
          </div>

          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
            <FactorCard
              label={view === 'day' ? 'Deep sleep' : 'Avg deep'}
              value={formatPct(view === 'day' ? dayNight?.deep : summary.avgDeep)}
              hint={view === 'day' ? 'Share of overnight sleep' : `${view} average`}
              accent={STAGE_COLORS.deep}
              onClick={() => setActiveFactor('deep')}
            />
            <FactorCard
              label={view === 'day' ? 'REM sleep' : 'Avg REM'}
              value={formatPct(view === 'day' ? dayNight?.rem : summary.avgRem)}
              hint={view === 'day' ? 'Share of overnight sleep' : `${view} average`}
              accent={STAGE_COLORS.rem}
              onClick={() => setActiveFactor('rem')}
            />
            <FactorCard
              label={view === 'day' ? 'Awake' : 'Avg awake'}
              value={
                view === 'day'
                  ? `${formatMinutes(dayNight?.awake)}${
                      dayNight?.awakeCount != null
                        ? ``
                        : ''
                    }`
                  : formatMinutes(summary.avgAwake)
              }
              hint={view === 'day' ? 'Wakefulness overnight' : `${view} average`}
              accent={STAGE_COLORS.awake}
              onClick={() => setActiveFactor('awake')}
            />
            <FactorCard
              label={view === 'day' ? 'Total nap time' : 'Avg total nap'}
              value={formatMinutes(view === 'day' ? dayNight?.nap : summary.avgNap)}
              hint={
                view === 'day'
                  ? dayNight?.nap != null
                    ? 'Nap session length from sync'
                    : 'No nap logged'
                  : `${view} average`
              }
              accent={STAGE_COLORS.light}
              onClick={() => setActiveFactor('nap')}
              onInfoClick={() => setActiveFactor('nap')}
              infoLabel="Why Total nap time can differ from the COROS app"
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
              accent="#6366F1"
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
                  <div className="rounded-xl border border-[var(--aal-line)] px-2 py-3">
                    <p className="text-[var(--aal-muted)]">Deep</p>
                    <p className="mt-1 font-semibold tabular-nums" style={{ color: STAGE_COLORS.deep }}>
                      {formatPct(summary.avgDeep)}
                    </p>
                  </div>
                  <div className="rounded-xl border border-[var(--aal-line)] px-2 py-3">
                    <p className="text-[var(--aal-muted)]">Light</p>
                    <p className="mt-1 font-semibold tabular-nums" style={{ color: STAGE_COLORS.light }}>
                      {formatPct(summary.avgLight)}
                    </p>
                  </div>
                  <div className="rounded-xl border border-[var(--aal-line)] px-2 py-3">
                    <p className="text-[var(--aal-muted)]">REM</p>
                    <p className="mt-1 font-semibold tabular-nums" style={{ color: STAGE_COLORS.rem }}>
                      {formatPct(summary.avgRem)}
                    </p>
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
                  accent={SLEEP_CHART.hrv}
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
                  accent={SLEEP_CHART.sleepHr}
                  onClick={() => setActiveFactor('sleepHr')}
                />
              </div>
              {view !== 'day' ? (
                <div className="mt-4 h-44">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={chartPoints}>
                      <CartesianGrid stroke={SLEEP_CHART.grid} strokeDasharray="4 6" vertical={false} />
                      <XAxis
                        dataKey="labelShort"
                        tick={{ fontSize: 11, fill: 'var(--aal-muted)' }}
                        stroke="transparent"
                        tickLine={false}
                      />
                      <YAxis
                        tick={{ fontSize: 11, fill: 'var(--aal-muted)' }}
                        stroke="transparent"
                        tickLine={false}
                        axisLine={false}
                      />
                      <Tooltip
                        cursor={{ stroke: SLEEP_CHART.duration, strokeWidth: 1, strokeDasharray: '4 4' }}
                        content={
                          <SleepTooltip
                            labelFormatter={(_, payload) => payload?.[0]?.payload?.date || _}
                            valueFormatter={(value, name) => [
                              name === 'HRV'
                                ? formatNumber(value, 0, ' ms')
                                : formatNumber(value, 0, ' bpm'),
                              name,
                            ]}
                          />
                        }
                      />
                      <Line
                        type="monotone"
                        dataKey="hrv"
                        name="HRV"
                        stroke={SLEEP_CHART.hrv}
                        strokeWidth={2.5}
                        dot={chartPoints.length <= 14}
                        activeDot={{ r: 5, strokeWidth: 2, stroke: '#fff' }}
                        connectNulls
                      />
                      <Line
                        type="monotone"
                        dataKey="sleepHr"
                        name="Sleep HR"
                        stroke={SLEEP_CHART.sleepHr}
                        strokeWidth={2.2}
                        dot={chartPoints.length <= 14}
                        activeDot={{ r: 5, strokeWidth: 2, stroke: '#fff' }}
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
              subtitle="Total sleep duration vs recent nights."
            >
              <div className="h-64 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={compareNights} barCategoryGap="28%">
                    <CartesianGrid stroke={SLEEP_CHART.grid} strokeDasharray="4 6" vertical={false} />
                    <XAxis
                      dataKey="date"
                      tick={{ fontSize: 11, fill: 'var(--aal-muted)' }}
                      stroke="transparent"
                      tickLine={false}
                      tickFormatter={(value) => formatDayLabel(value, 'weekday')}
                    />
                    <YAxis
                      tick={{ fontSize: 11, fill: 'var(--aal-muted)' }}
                      stroke="transparent"
                      tickLine={false}
                      axisLine={false}
                    />
                    <Tooltip
                      cursor={{ fill: SLEEP_CHART.cursor }}
                      content={
                        <SleepTooltip
                          labelFormatter={(value) => formatDayLabel(value, 'full')}
                          valueFormatter={(value) => [formatMinutes(value), 'Duration']}
                        />
                      }
                    />
                    <Bar
                      dataKey="duration"
                      name="Duration"
                      fill={SLEEP_CHART.duration}
                      radius={[10, 10, 4, 4]}
                      activeBar={SleepBarActive}
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
                    ? 'Weekly average duration across the year.'
                    : `Daily total sleep for this ${view}.`
                }
              >
                <div className="h-72 w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={chartPoints}>
                      <defs>
                        <linearGradient id="sleepDurationFill" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="0%" stopColor={SLEEP_CHART.duration} stopOpacity={0.35} />
                          <stop offset="100%" stopColor={SLEEP_CHART.duration} stopOpacity={0.02} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid stroke={SLEEP_CHART.grid} strokeDasharray="4 6" vertical={false} />
                      <XAxis
                        dataKey="labelShort"
                        tick={{ fontSize: 11, fill: 'var(--aal-muted)' }}
                        stroke="transparent"
                        tickLine={false}
                      />
                      <YAxis
                        tick={{ fontSize: 11, fill: 'var(--aal-muted)' }}
                        stroke="transparent"
                        tickLine={false}
                        axisLine={false}
                      />
                      <Tooltip
                        cursor={{ stroke: SLEEP_CHART.duration, strokeWidth: 1, strokeDasharray: '4 4' }}
                        content={
                          <SleepTooltip
                            labelFormatter={(_, payload) => payload?.[0]?.payload?.date || _}
                            valueFormatter={(value) => [formatMinutes(value), 'Duration']}
                          />
                        }
                      />
                      <Area
                        type="monotone"
                        dataKey="duration"
                        name="Duration"
                        stroke={SLEEP_CHART.duration}
                        fill="url(#sleepDurationFill)"
                        strokeWidth={2.75}
                        dot={chartPoints.length <= 16}
                        activeDot={{ r: 5, strokeWidth: 2, stroke: '#fff' }}
                        connectNulls
                      />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              </SectionCard>

              <SectionCard
                title={view === 'year' ? 'Weekly stage mix' : `${view} stage mix over time`}
                subtitle="Stacked minutes — Deep, Light, REM, and Awake."
              >
                <div className="h-72 w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={chartPoints} barCategoryGap="18%">
                      <CartesianGrid stroke={SLEEP_CHART.grid} strokeDasharray="4 6" vertical={false} />
                      <XAxis
                        dataKey="labelShort"
                        tick={{ fontSize: 11, fill: 'var(--aal-muted)' }}
                        stroke="transparent"
                        tickLine={false}
                      />
                      <YAxis
                        tick={{ fontSize: 11, fill: 'var(--aal-muted)' }}
                        stroke="transparent"
                        tickLine={false}
                        axisLine={false}
                      />
                      <Tooltip
                        cursor={{ fill: SLEEP_CHART.cursor }}
                        content={
                          <SleepTooltip
                            labelFormatter={(_, payload) => payload?.[0]?.payload?.date || _}
                            valueFormatter={(value, name) => [formatMinutes(value), name]}
                          />
                        }
                      />
                      <Bar dataKey="deepMin" name="Deep" stackId="stages" fill={STAGE_COLORS.deep} radius={[0, 0, 0, 0]} />
                      <Bar dataKey="lightMin" name="Light" stackId="stages" fill={STAGE_COLORS.light} />
                      <Bar dataKey="remMin" name="REM" stackId="stages" fill={STAGE_COLORS.rem} />
                      <Bar
                        dataKey="awakeMin"
                        name="Awake"
                        stackId="stages"
                        fill={STAGE_COLORS.awake}
                        radius={[6, 6, 0, 0]}
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
