import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { getCoachStatus, getWeekBrief } from '../api/coach'
import { backfillMetricHistory, getCoachContext, getMetricSeries } from '../api/coros'
import { WeekAlertButton } from '../components/coach/TodayAdvice'
import StressGauge from '../components/health/StressGauge'
import StressZoneStrip from '../components/health/StressZoneStrip'
import AppShell from '../components/layout/AppShell'
import LearnRow from '../components/training/LearnRow'
import LoadEquation from '../components/training/LoadEquation'
import EmptyState from '../components/ui/EmptyState'
import LoadingDots from '../components/ui/LoadingDots'
import RangeTabs from '../components/ui/RangeTabs'
import SectionCard from '../components/ui/SectionCard'
import {
  STRESS_LEARN,
  STRESS_ZONES,
  interpretStress,
  summarizeStressPoints,
} from '../utils/stressGuides'
import { HEALTH_CHART, healthColorsForMetric } from '../utils/healthTheme'
import { staggerContainer, staggerItem } from '../utils/statusColors'

const COLORS = healthColorsForMetric('stress')

const RANGE_DAYS = {
  '7d': 7,
  '4w': 28,
  '3m': 90,
  '6m': 180,
  '1y': 365,
  all: 365,
}

function toISODate(value) {
  if (!value) return null
  if (typeof value === 'string') return value.slice(0, 10)
  return null
}

function addDays(isoDate, days) {
  const date = new Date(`${isoDate}T12:00:00`)
  date.setDate(date.getDate() + days)
  return date.toISOString().slice(0, 10)
}

function daysBetween(fromIso, toIso) {
  const from = new Date(`${fromIso}T12:00:00`)
  const to = new Date(`${toIso}T12:00:00`)
  return Math.max(0, Math.round((to - from) / 86400000))
}

function tickIntervalForSpan(pointCount) {
  if (pointCount <= 14) return 0
  if (pointCount <= 45) return 3
  if (pointCount <= 100) return 6
  if (pointCount <= 200) return 13
  return 29
}

function buildChartDomain(series, range) {
  const byDate = new Map()
  for (const point of series?.points || []) {
    const key = toISODate(point.date)
    if (!key) continue
    byDate.set(key, point)
  }
  const valued = (series?.points || []).filter((point) => point.value != null && point.date)
  let start = toISODate(series?.from_date)
  let end = toISODate(series?.to_date)
  if (range === 'all' || range === '1y') {
    if (valued.length) {
      const dates = valued.map((point) => toISODate(point.date)).filter(Boolean).sort()
      start = dates[0]
      end = range === 'all' ? dates[dates.length - 1] : end || dates[dates.length - 1]
    }
  }
  if (!start || !end) {
    const today = new Date().toISOString().slice(0, 10)
    end = end || today
    start = start || addDays(end, -(RANGE_DAYS[range] || 28))
  }
  const span = daysBetween(start, end)
  const rows = []
  for (let i = 0; i <= span; i += 1) {
    const date = addDays(start, i)
    const point = byDate.get(date)
    rows.push({
      date,
      labelShort: date.slice(5),
      value: point?.value ?? null,
      label: point?.label ?? null,
      meta: point?.meta || {},
    })
  }
  return rows
}

function formatPts(value) {
  if (value == null || Number.isNaN(Number(value))) return '—'
  return `${Math.round(Number(value))}`
}

function StressTooltip({ active, payload }) {
  if (!active || !payload?.length) return null
  const row = payload[0]?.payload
  if (!row) return null
  return (
    <div
      className="rounded-xl border px-3 py-2.5 shadow-lg backdrop-blur-sm"
      style={{
        background: 'color-mix(in srgb, var(--aal-card) 92%, transparent)',
        borderColor: 'var(--aal-line)',
      }}
    >
      <p className="text-[11px] font-semibold text-[var(--aal-muted)]">{row.date}</p>
      <div className="mt-1.5 flex items-center gap-2 text-xs">
        <span className="size-2 shrink-0 rounded-full" style={{ background: COLORS.primary }} />
        <span className="text-[var(--aal-muted)]">Daily stress</span>
        <span className="ml-auto font-semibold tabular-nums text-[var(--aal-ink)]">
          {row.value == null ? '—' : Math.round(row.value)}
        </span>
      </div>
    </div>
  )
}

export default function StressPage() {
  const [range, setRange] = useState('4w')
  const [series, setSeries] = useState(null)
  const [context, setContext] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [backfilling, setBackfilling] = useState(false)
  const [focusZone, setFocusZone] = useState(null)
  const [openLearn, setOpenLearn] = useState('what')
  const [brief, setBrief] = useState(null)
  const [briefLoading, setBriefLoading] = useState(false)
  const [briefError, setBriefError] = useState('')
  const [consented, setConsented] = useState(false)

  const loadBrief = useCallback(async (force = false) => {
    setBriefLoading(true)
    setBriefError('')
    try {
      setBrief(await getWeekBrief({ refresh: Boolean(force), topic: 'stress' }))
    } catch (err) {
      setBriefError(err.message || "Could not load this week’s stress brief.")
    } finally {
      setBriefLoading(false)
    }
  }, [])

  useEffect(() => {
    let cancelled = false
    async function boot() {
      setError('')
      try {
        const [statusResult, contextResult] = await Promise.all([
          getCoachStatus().catch(() => null),
          getCoachContext().catch(() => null),
        ])
        if (cancelled) return
        setContext(contextResult)
        const aiOn = Boolean(statusResult?.ai_consent)
        setConsented(aiOn)
        if (aiOn) loadBrief(false)
        else setBriefError('Turn on AI coaching in settings to get a stress brief.')
      } catch (err) {
        if (!cancelled) setError(err.message || 'Failed to load stress.')
      }
    }
    boot()
    return () => {
      cancelled = true
    }
  }, [loadBrief])

  useEffect(() => {
    let cancelled = false
    async function loadSeries() {
      setLoading(true)
      setError('')
      try {
        const seriesResult = await getMetricSeries('stress', range)
        if (!cancelled) setSeries(seriesResult)
      } catch (err) {
        if (!cancelled) setError(err.message || 'Failed to load stress.')
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    loadSeries()
    return () => {
      cancelled = true
    }
  }, [range])

  const chartData = useMemo(() => buildChartDomain(series, range), [series, range])
  const stats = useMemo(() => summarizeStressPoints(series?.points || []), [series])
  const latestHealth = context?.coros?.latest_health
  const today = latestHealth?.stress ?? stats.today
  const story = useMemo(
    () =>
      interpretStress({
        today,
        usual7: stats.usual7,
        usual28: stats.usual28,
        days: stats.days,
      }),
    [today, stats],
  )

  const activeZoneId = focusZone || story.zone.id
  const activeGuide = STRESS_ZONES.find((zone) => zone.id === activeZoneId) || story.zoneGuide
  const empty = !loading && stats.days === 0
  const tickInterval = tickIntervalForSpan(chartData.length)
  const fitness = context?.coros?.fitness

  async function handleExploreHistory() {
    setBackfilling(true)
    setError('')
    try {
      setSeries(await backfillMetricHistory('stress', range === '7d' ? '4w' : range))
    } catch (err) {
      setError(err.message || 'Failed to backfill stress history.')
    } finally {
      setBackfilling(false)
    }
  }

  return (
    <AppShell title="Stress" fill>
      <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
        <header className="relative z-20 flex shrink-0 flex-wrap items-center justify-between gap-2 border-b border-[var(--aal-line)] bg-[var(--aal-card)]/85 px-3 py-2 backdrop-blur-sm sm:px-5">
          <div className="min-w-0 pl-10 lg:pl-0">
            <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-indigo-500 dark:text-indigo-300">
              Health
            </p>
            <p className="truncate text-sm font-semibold text-[var(--aal-ink)]">Stress</p>
            <p className="truncate text-[11px] text-[var(--aal-muted)]">
              Today’s all-day load vs the week your body is used to
            </p>
          </div>
          <WeekAlertButton
            topic="stress"
            advice={brief}
            loading={briefLoading && !brief}
            error={briefError}
            onRefresh={() => (consented ? loadBrief(true) : null)}
            refreshing={briefLoading}
            health={latestHealth}
            fitness={fitness}
            loadChips={[
              { label: 'Today', value: today != null ? formatPts(today) : null },
              {
                label: '7-day usual',
                value: stats.usual7 != null ? formatPts(stats.usual7) : null,
              },
              {
                label: 'Vs usual',
                value: story.ratio != null ? Number(story.ratio).toFixed(2) : null,
              },
            ]}
          />
        </header>

        {error ? (
          <p className="shrink-0 border-b border-red-200/60 bg-red-50/80 px-4 py-2 text-sm text-danger-muted">
            {error}
          </p>
        ) : null}

        {loading ? (
          <div className="flex min-h-0 flex-1 items-center justify-center">
            <LoadingDots label="Loading stress…" />
          </div>
        ) : (
          <div className="min-h-0 flex-1 overflow-y-auto px-4 py-6 sm:px-6 lg:px-8">
            <motion.div
              className="space-y-8"
              variants={staggerContainer}
              initial="hidden"
              animate="visible"
            >
              {empty ? (
                <motion.div variants={staggerItem}>
                  <EmptyState
                    title="No daily stress yet"
                    description="Connect COROS and sync daily health so stress averages land here. Compare days to your own usual — not someone else’s 0–100 number."
                    actionLabel="Connect COROS"
                    actionTo="/connect-coros"
                  />
                </motion.div>
              ) : null}

              <motion.div variants={staggerItem} className="grid gap-6 xl:grid-cols-5">
                <SectionCard
                  className="xl:col-span-3"
                  title="Today vs usual"
                  subtitle="Daily average stress divided by your 7-day mean. 1.00 means you matched the week. Higher is more loaded."
                >
                  <LoadEquation
                    accent="health"
                    mobileHint="Today ÷ 7-day usual = vs usual"
                    cells={[
                      {
                        hint: 'COROS daily average · newest day',
                        label: 'Today',
                        value: formatPts(today),
                        unit: '',
                      },
                      {
                        hint: 'Mean of last 7 days',
                        label: 'Usual',
                        value: formatPts(stats.usual7),
                        unit: '',
                      },
                      {
                        hint: 'Today ÷ usual',
                        label: 'Vs usual',
                        value: story.ratio == null ? '—' : Number(story.ratio).toFixed(2),
                        unit: '',
                      },
                    ]}
                  />
                  <div className="mt-6">
                    <StressZoneStrip
                      ratio={story.ratio}
                      today={today}
                      activeId={activeZoneId}
                      onSelect={setFocusZone}
                    />
                  </div>
                  {activeGuide ? (
                    <p className="mt-4 text-sm leading-relaxed text-[var(--aal-muted)]">
                      <span className="font-semibold text-[var(--aal-ink)]">{activeGuide.label}. </span>
                      {activeGuide.meaning}
                    </p>
                  ) : null}
                  {today != null && Number(today) >= 70 ? (
                    <p className="mt-3 text-sm text-[var(--aal-ink)]/80">
                      Absolute reading is 70 or higher — that is our safety flag, even if the week’s
                      average is also high.
                    </p>
                  ) : null}
                  {stats.days > 0 && stats.days < 5 ? (
                    <p className="mt-3 text-sm leading-relaxed text-[var(--aal-ink)]/80">
                      Only {stats.days} day{stats.days === 1 ? '' : 's'} with stress so far. The usual
                      number is still forming — a spike here is a hint, not a verdict.
                    </p>
                  ) : null}
                  <p className="mt-4 text-sm leading-relaxed text-[var(--aal-ink)]">
                    {story.headline}. {story.body}
                  </p>
                </SectionCard>

                <SectionCard
                  className="xl:col-span-2"
                  title="Gauge"
                  subtitle="Same vs-usual number on a 0.70–1.40 scale. Typical sits in the indigo band."
                >
                  <StressGauge ratio={story.ratio} today={today} />
                </SectionCard>
              </motion.div>

              <motion.div variants={staggerItem}>
                <SectionCard
                  title="Daily stress trend"
                  subtitle="Each point is an all-day average. The dashed line is your 7-day usual."
                  actions={
                    <div className="flex flex-wrap items-center gap-2">
                      <RangeTabs value={range} onChange={setRange} variant="health" />
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
                >
                  {chartData.some((row) => row.value != null) ? (
                    <div className="h-72">
                      <ResponsiveContainer width="100%" height="100%">
                        <LineChart data={chartData} margin={{ top: 12, right: 8, left: 0, bottom: 0 }}>
                          <CartesianGrid
                            stroke={HEALTH_CHART.grid}
                            strokeDasharray="4 6"
                            vertical={false}
                          />
                          <XAxis
                            dataKey="labelShort"
                            tick={{ fontSize: 11, fill: 'var(--aal-muted)' }}
                            axisLine={false}
                            tickLine={false}
                            interval={tickInterval}
                            minTickGap={16}
                          />
                          <YAxis
                            tick={{ fontSize: 12, fill: 'var(--aal-muted)' }}
                            axisLine={false}
                            tickLine={false}
                            width={44}
                            tickFormatter={(value) => `${value}`}
                          />
                          <Tooltip
                            cursor={{
                              stroke: HEALTH_CHART.cursorStroke,
                              strokeWidth: 1,
                              strokeDasharray: '4 4',
                            }}
                            content={<StressTooltip />}
                          />
                          {stats.usual7 != null ? (
                            <ReferenceLine
                              y={stats.usual7}
                              stroke="#818CF8"
                              strokeDasharray="4 4"
                              label={{
                                value: '7-day usual',
                                position: 'insideTopRight',
                                fill: '#6366F1',
                                fontSize: 11,
                              }}
                            />
                          ) : null}
                          <Line
                            type="monotone"
                            dataKey="value"
                            name="Daily stress"
                            stroke={COLORS.primary}
                            strokeWidth={2.5}
                            dot={chartData.filter((row) => row.value != null).length <= 14}
                            connectNulls={false}
                            activeDot={{ r: 4, fill: COLORS.primary }}
                          />
                        </LineChart>
                      </ResponsiveContainer>
                    </div>
                  ) : (
                    <p className="py-10 text-sm text-[var(--aal-muted)]">
                      No daily points in this window. Try a wider range or explore history.
                    </p>
                  )}
                </SectionCard>
              </motion.div>

              <motion.section variants={staggerItem}>
                <h2 className="text-lg font-semibold text-[var(--aal-ink)]">What this means for workouts</h2>
                <p className="mt-1 max-w-2xl text-sm text-[var(--aal-muted)]">
                  Tap a zone on the strip, or read your current one. Daily stress is all-day autonomic
                  load — it does not replace kilometres, effort load, or overnight HRV.
                </p>
                <div className="mt-4 grid gap-3 md:grid-cols-2">
                  {STRESS_ZONES.map((zone) => {
                    const current = zone.id === activeZoneId
                    return (
                      <button
                        key={zone.id}
                        type="button"
                        onClick={() => setFocusZone(zone.id)}
                        className={`rounded-2xl border p-4 text-left transition ${
                          current
                            ? 'border-indigo-300/40 bg-[var(--aal-card)] shadow-sm'
                            : 'border-[var(--aal-line)] bg-[var(--aal-card)]/60 opacity-80 hover:opacity-100'
                        }`}
                      >
                        <div className="flex items-center justify-between gap-2">
                          <p className="text-sm font-semibold text-[var(--aal-ink)]">{zone.label}</p>
                          <span className="text-[10px] font-medium uppercase tracking-[0.14em] text-[var(--aal-muted)]">
                            {zone.range}
                          </span>
                        </div>
                        <p className="mt-2 text-sm leading-relaxed text-[var(--aal-muted)]">{zone.workouts}</p>
                        <p className="mt-3 text-sm leading-relaxed text-[var(--aal-ink)]/80">
                          <span className="font-semibold">Make it better. </span>
                          {zone.improve}
                        </p>
                      </button>
                    )
                  })}
                </div>
              </motion.section>

              <motion.section
                variants={staggerItem}
                className="rounded-2xl border border-[var(--aal-line)] bg-[var(--aal-card)] px-5 sm:px-6"
              >
                <div className="pt-5">
                  <h2 className="text-lg font-semibold text-[var(--aal-ink)]">The science, without the jargon</h2>
                  <p className="mt-1 text-sm text-[var(--aal-muted)]">
                    Short answers first, then the papers. This is all-day stress versus your own
                    baseline — not a diagnosis and not medical advice.
                  </p>
                </div>
                {STRESS_LEARN.map((topic) => (
                  <LearnRow
                    key={topic.id}
                    topic={topic}
                    open={openLearn === topic.id}
                    onToggle={() => setOpenLearn((current) => (current === topic.id ? null : topic.id))}
                  />
                ))}
              </motion.section>

              <motion.p variants={staggerItem} className="text-sm text-[var(--aal-muted)]">
                Overnight recovery lives on{' '}
                <Link to="/health/hrv" className="font-medium text-indigo-500 dark:text-indigo-300">
                  HRV
                </Link>
                {' '}and{' '}
                <Link to="/health/sleep" className="font-medium text-indigo-500 dark:text-indigo-300">
                  Sleep
                </Link>
                . Resting HR is the companion signal on{' '}
                <Link to="/health/rhr" className="font-medium text-indigo-500 dark:text-indigo-300">
                  Resting HR
                </Link>
                .
              </motion.p>
            </motion.div>
          </div>
        )}
      </div>
    </AppShell>
  )
}
