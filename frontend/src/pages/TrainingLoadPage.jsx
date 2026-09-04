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
import { getCoachContext, getMetricSeries } from '../api/coros'
import { WeekAlertButton } from '../components/coach/TodayAdvice'
import AppShell from '../components/layout/AppShell'
import ACWRGauge from '../components/ACWRGauge'
import AcwrZoneStrip from '../components/training/AcwrZoneStrip'
import LearnRow from '../components/training/LearnRow'
import LoadEquation from '../components/training/LoadEquation'
import EmptyState from '../components/ui/EmptyState'
import LoadingDots from '../components/ui/LoadingDots'
import SectionCard from '../components/ui/SectionCard'
import { EFFORT_LEARN, EFFORT_ZONES, interpretEffortLoad } from '../utils/loadGuides'
import { staggerContainer, staggerItem } from '../utils/statusColors'

function formatLoad(value, digits = 0) {
  if (value == null || Number.isNaN(Number(value))) return '—'
  return Number(value).toFixed(digits)
}

function commentText(entry) {
  if (entry == null) return ''
  if (typeof entry === 'string') return entry
  return entry.comment || entry.text || ''
}

function RatioTooltip({ active, payload }) {
  if (!active || !payload?.length) return null
  const row = payload[0]?.payload
  if (!row) return null
  return (
    <div className="rounded-xl border border-[var(--aal-line)] bg-[var(--aal-card)] px-3 py-2 text-xs shadow-sm">
      <p className="font-semibold text-[var(--aal-ink)]">{row.date}</p>
      <p className="mt-1 text-[var(--aal-muted)]">Ratio {formatLoad(row.ratio, 2)}</p>
      {row.short != null ? (
        <p className="text-[var(--aal-muted)]">Short {formatLoad(row.short, 0)}</p>
      ) : null}
      {row.long != null ? (
        <p className="text-[var(--aal-muted)]">Long {formatLoad(row.long, 0)}</p>
      ) : null}
      {row.note ? <p className="mt-1 text-[var(--aal-ink)]/80">{row.note}</p> : null}
    </div>
  )
}

export default function TrainingLoadPage() {
  const [series, setSeries] = useState(null)
  const [context, setContext] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [focusZone, setFocusZone] = useState(null)
  const [openLearn, setOpenLearn] = useState('ratio')
  const [brief, setBrief] = useState(null)
  const [briefLoading, setBriefLoading] = useState(false)
  const [briefError, setBriefError] = useState('')
  const [consented, setConsented] = useState(false)

  const loadBrief = useCallback(async (force = false) => {
    setBriefLoading(true)
    setBriefError('')
    try {
      setBrief(await getWeekBrief({ refresh: Boolean(force), topic: 'load' }))
    } catch (err) {
      setBriefError(err.message || "Could not load this week’s brief.")
    } finally {
      setBriefLoading(false)
    }
  }, [])

  useEffect(() => {
    let cancelled = false
    async function boot() {
      setLoading(true)
      setError('')
      try {
        const [seriesResult, statusResult, contextResult] = await Promise.all([
          getMetricSeries('load', 'all'),
          getCoachStatus().catch(() => null),
          getCoachContext().catch(() => null),
        ])
        if (cancelled) return
        setSeries(seriesResult)
        setContext(contextResult)
        const aiOn = Boolean(statusResult?.ai_consent)
        setConsented(aiOn)
        if (aiOn) loadBrief(false)
        else setBriefError('Turn on AI coaching in settings to get a week brief.')
      } catch (err) {
        if (!cancelled) setError(err.message || 'Failed to load training load.')
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    boot()
    return () => {
      cancelled = true
    }
  }, [loadBrief])

  const loadSnap = context?.coros?.training_load || {}
  const latest = series?.latest || {}
  const ratio = loadSnap.load_ratio ?? latest.load_ratio ?? latest.value ?? null
  const shortLoad = loadSnap.short_load ?? latest.short_load ?? latest.secondary ?? null
  const longLoad = loadSnap.long_load ?? latest.long_load ?? latest.meta?.long_load ?? null

  const story = useMemo(
    () => interpretEffortLoad({ ratio, shortLoad, longLoad }),
    [ratio, shortLoad, longLoad],
  )

  const chartData = useMemo(() => {
    return (series?.points || [])
      .filter((point) => point.value != null && point.date)
      .map((point) => ({
        date: String(point.date).slice(0, 10),
        labelShort: String(point.date).slice(5, 10),
        ratio: Number(point.value),
        short: point.secondary ?? point.meta?.short_load ?? null,
        long: point.meta?.long_load ?? null,
        note: point.label || null,
      }))
  }, [series])

  const comments = useMemo(() => {
    const raw = loadSnap.daily_comments
    const fromSync = Array.isArray(raw)
      ? raw
          .map((entry) => {
            if (typeof entry === 'string') return { date: null, text: entry }
            return {
              date: entry.date || null,
              text: commentText(entry),
              ratio: entry.load_ratio,
            }
          })
          .filter((entry) => entry.text)
      : []
    if (fromSync.length) return fromSync
    return chartData
      .filter((row) => row.note)
      .map((row) => ({ date: row.date, text: row.note, ratio: row.ratio }))
  }, [loadSnap, chartData])

  const activeZoneId = focusZone || story.zone.id
  const activeGuide = EFFORT_ZONES.find((zone) => zone.id === activeZoneId) || story.zoneGuide
  const ready = !loading
  const empty = ready && ratio == null && chartData.length === 0
  const fitness = context?.coros?.fitness
  const sparse = chartData.length > 0 && chartData.length < 3

  return (
    <AppShell title="Training Load" fill>
      <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
        <header className="relative z-20 flex shrink-0 flex-wrap items-center justify-between gap-2 border-b border-[var(--aal-line)] bg-[var(--aal-card)]/85 px-3 py-2 backdrop-blur-sm sm:px-5">
          <div className="min-w-0 pl-10 lg:pl-0">
            <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-sage">Training</p>
            <p className="truncate text-sm font-semibold text-[var(--aal-ink)]">Training Load</p>
            <p className="truncate text-[11px] text-[var(--aal-muted)]">
              Recent effort vs the fitness COROS has stored
            </p>
          </div>
          <WeekAlertButton
            topic="load"
            advice={brief}
            loading={briefLoading && !brief}
            error={briefError}
            onRefresh={() => (consented ? loadBrief(true) : null)}
            refreshing={briefLoading}
            health={context?.coros?.latest_health}
            fitness={fitness}
            loadChips={[
              { label: 'Ratio', value: ratio != null ? Number(ratio).toFixed(2) : null },
              { label: 'Short', value: shortLoad != null ? String(Math.round(shortLoad)) : null },
              { label: 'Long', value: longLoad != null ? String(Math.round(longLoad)) : null },
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
            <LoadingDots label="Loading training load…" />
          </div>
        ) : ready ? (
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
                    title="No COROS load yet"
                    description="Connect COROS and sync so short-term, long-term, and the load ratio show up here. This is effort, not kilometres."
                    actionLabel="Connect COROS"
                    actionTo="/connect-coros"
                  />
                </motion.div>
              ) : null}

              <motion.div variants={staggerItem} className="grid gap-6 xl:grid-cols-5">
                <SectionCard
                  className="xl:col-span-3"
                  title="The ratio"
                  subtitle="Recent effort divided by the fitness base COROS has stored."
                >
                  <LoadEquation
                    mobileHint="Short-term ÷ long-term = load ratio"
                    cells={[
                      {
                        hint: 'Short-term · recent effort',
                        label: 'Recent days',
                        value: formatLoad(shortLoad, 0),
                        unit: '',
                      },
                      {
                        hint: 'Long-term · fitness base',
                        label: 'Your base',
                        value: formatLoad(longLoad, 0),
                        unit: '',
                      },
                      {
                        hint: 'Load ratio',
                        label: 'Ratio',
                        value: formatLoad(ratio, 2),
                        unit: '',
                      },
                    ]}
                  />
                  <div className="mt-6">
                    <AcwrZoneStrip
                      acwr={ratio}
                      activeId={activeZoneId}
                      onSelect={setFocusZone}
                      zones={EFFORT_ZONES}
                    />
                  </div>
                  {activeGuide ? (
                    <p className="mt-4 text-sm leading-relaxed text-[var(--aal-muted)]">
                      <span className="font-semibold text-[var(--aal-ink)]">{activeGuide.label}. </span>
                      {activeGuide.meaning}
                    </p>
                  ) : null}
                  {sparse ? (
                    <p className="mt-3 text-sm leading-relaxed text-[var(--aal-ink)]/80">
                      COROS usually sends about a week of load comments per sync. Sync regularly so
                      the chart fills in — a high ratio on a thin history is a hint, not a verdict.
                    </p>
                  ) : null}
                </SectionCard>

                <SectionCard
                  className="xl:col-span-2"
                  title="Gauge"
                  subtitle="Same 0–2 scale as Volume & ACWR. Sweet spot sits in the middle."
                >
                  <ACWRGauge acwr={ratio} embedded title="Load ratio" />
                </SectionCard>
              </motion.div>

              <motion.div variants={staggerItem}>
                <SectionCard
                  title="Recent load ratio"
                  subtitle="Each point is a COROS day. The line at 1.0 is a matched week — recent effort equals your base."
                >
                  {chartData.length ? (
                    <div className="h-72">
                      <ResponsiveContainer width="100%" height="100%">
                        <LineChart data={chartData} margin={{ top: 12, right: 8, left: 0, bottom: 0 }}>
                          <CartesianGrid stroke="var(--aal-line)" strokeDasharray="3 3" vertical={false} />
                          <XAxis
                            dataKey="labelShort"
                            tick={{ fontSize: 12, fill: 'var(--aal-muted)' }}
                            axisLine={false}
                            tickLine={false}
                          />
                          <YAxis
                            tick={{ fontSize: 12, fill: 'var(--aal-muted)' }}
                            axisLine={false}
                            tickLine={false}
                            width={40}
                            domain={[0, (dataMax) => Math.max(2, Number(dataMax) || 0)]}
                            allowDecimals
                          />
                          <Tooltip cursor={{ stroke: 'var(--aal-line)' }} content={<RatioTooltip />} />
                          <ReferenceLine
                            y={1}
                            stroke="var(--aal-muted)"
                            strokeDasharray="4 4"
                            label={{
                              value: 'Balanced',
                              position: 'insideTopRight',
                              fill: 'var(--aal-muted)',
                              fontSize: 11,
                            }}
                          />
                          <Line
                            type="monotone"
                            dataKey="ratio"
                            name="Load ratio"
                            stroke="#6b9080"
                            strokeWidth={2.5}
                            dot={chartData.length <= 14}
                            connectNulls
                            activeDot={{ r: 4 }}
                          />
                        </LineChart>
                      </ResponsiveContainer>
                    </div>
                  ) : (
                    <p className="py-10 text-sm text-[var(--aal-muted)]">
                      No daily load points yet. Sync COROS to pull the latest comments.
                    </p>
                  )}
                </SectionCard>
              </motion.div>

              {comments.length ? (
                <motion.div variants={staggerItem}>
                  <SectionCard
                    title="COROS daily comments"
                    subtitle="Official notes from the last sync — about a week of days."
                  >
                    <ul className="space-y-2">
                      {comments.slice(0, 8).map((entry, index) => (
                        <li
                          key={`${entry.date || 'c'}-${index}`}
                          className="rounded-xl border border-[var(--aal-line)] bg-[var(--aal-bg)] px-3 py-2.5"
                        >
                          <div className="flex flex-wrap items-baseline justify-between gap-2">
                            <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-sage">
                              {entry.date || 'Note'}
                            </p>
                            {entry.ratio != null ? (
                              <p className="text-xs tabular-nums text-[var(--aal-muted)]">
                                Ratio {Number(entry.ratio).toFixed(2)}
                              </p>
                            ) : null}
                          </div>
                          <p className="mt-1 text-sm leading-relaxed text-[var(--aal-ink)]/90">
                            {entry.text}
                          </p>
                        </li>
                      ))}
                    </ul>
                  </SectionCard>
                </motion.div>
              ) : null}

              <motion.section variants={staggerItem}>
                <h2 className="text-lg font-semibold text-[var(--aal-ink)]">What this means for workouts</h2>
                <p className="mt-1 max-w-2xl text-sm text-[var(--aal-muted)]">
                  Tap a zone on the strip, or read your current one. Effort and kilometres are
                  separate — a “safe” ratio can still hide a nasty interval spike.
                </p>
                <div className="mt-4 grid gap-3 md:grid-cols-2">
                  {EFFORT_ZONES.map((zone) => {
                    const current = zone.id === activeZoneId
                    return (
                      <button
                        key={zone.id}
                        type="button"
                        onClick={() => setFocusZone(zone.id)}
                        className={`rounded-2xl border p-4 text-left transition ${
                          current
                            ? 'border-[var(--aal-ink)]/20 bg-[var(--aal-card)] shadow-sm'
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
                    Short answers first, then the papers. This is COROS effort load — the cousin of
                    distance ACWR, not a replacement, and not medical advice.
                  </p>
                </div>
                {EFFORT_LEARN.map((topic) => (
                  <LearnRow
                    key={topic.id}
                    topic={topic}
                    open={openLearn === topic.id}
                    onToggle={() => setOpenLearn((current) => (current === topic.id ? null : topic.id))}
                  />
                ))}
              </motion.section>

              <motion.p variants={staggerItem} className="text-sm text-[var(--aal-muted)]">
                For kilometres and ACWR from synced activities, see{' '}
                <Link to="/training/volume" className="font-medium text-[var(--aal-link)]">
                  Volume & ACWR
                </Link>
                .
              </motion.p>
            </motion.div>
          </div>
        ) : null}
      </div>
    </AppShell>
  )
}
