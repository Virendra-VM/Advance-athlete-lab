import { useEffect, useMemo, useState } from 'react'
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { backfillMetricHistory, getMetricSeries } from '../api/coros'
import AppShell from '../components/layout/AppShell'
import EmptyState from '../components/ui/EmptyState'
import LoadingDots from '../components/ui/LoadingDots'
import MetricExplainer from '../components/ui/MetricExplainer'
import PageHeader from '../components/ui/PageHeader'
import RangeTabs from '../components/ui/RangeTabs'
import SectionCard from '../components/ui/SectionCard'
import StatTile from '../components/ui/StatTile'
import { HEALTH_CHART, healthColorsForMetric } from '../utils/healthTheme'

const RANGE_DAYS = {
  '7d': 7,
  '4w': 28,
  '3m': 90,
  '6m': 180,
  '1y': 365,
  all: 365,
}

function formatValue(value, digits = 0, suffix = '') {
  if (value == null || Number.isNaN(Number(value))) return '—'
  return `${Number(value).toFixed(digits)}${suffix}`
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

/** Fill every day in the selected window so the X-axis matches the range tabs. */
function buildChartDomain(series, range, { dataOnly = false } = {}) {
  const valued = (series?.points || []).filter(
    (point) => point.value != null && point.date,
  )
  const byDate = new Map()
  for (const point of series?.points || []) {
    const key = toISODate(point.date)
    if (!key) continue
    byDate.set(key, point)
  }

  let start = toISODate(series?.from_date)
  let end = toISODate(series?.to_date)

  if (dataOnly || range === 'all') {
    if (valued.length) {
      const dates = valued.map((point) => toISODate(point.date)).filter(Boolean).sort()
      start = dates[0]
      end = dates[dates.length - 1]
    }
  }

  if (!start || !end) {
    const today = new Date().toISOString().slice(0, 10)
    end = end || today
    start = start || addDays(end, -(RANGE_DAYS[range] || 28))
  }

  // Never pad before the first real sample for long windows (1Y / All).
  if ((range === 'all' || range === '1y') && valued.length) {
    const first = valued
      .map((point) => toISODate(point.date))
      .filter(Boolean)
      .sort()[0]
    if (first && start < first) start = first
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
      secondary: point?.secondary ?? null,
      label: point?.label ?? null,
      meta: point?.meta || {},
    })
  }
  return rows
}

function tickIntervalForSpan(pointCount) {
  if (pointCount <= 14) return 0
  if (pointCount <= 45) return 3
  if (pointCount <= 100) return 6
  if (pointCount <= 200) return 13
  return 29
}

function HealthTooltip({ active, payload, label, labelFormatter, valueFormatter }) {
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
                style={{ background: entry.color || entry.fill || HEALTH_CHART.primary }}
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

export default function MetricPage({
  title,
  eyebrow = 'Health',
  description,
  metric,
  valueDigits = 0,
  valueSuffix = '',
  secondaryLabel = null,
  showSecondary = false,
  bare = false,
  showRangeTabs = true,
  theme = 'default',
}) {
  const health = theme === 'health'
  const colors = health
    ? healthColorsForMetric(metric)
    : { primary: '#6b9080', secondary: '#6b9ac4' }

  const [range, setRange] = useState(showRangeTabs ? '4w' : 'all')
  const [series, setSeries] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [backfilling, setBackfilling] = useState(false)

  useEffect(() => {
    let cancelled = false
    async function load() {
      setLoading(true)
      setError('')
      try {
        const data = await getMetricSeries(metric, showRangeTabs ? range : 'all')
        if (!cancelled) setSeries(data)
      } catch (err) {
        if (!cancelled) setError(err.message || 'Failed to load metric series.')
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    load()
    return () => {
      cancelled = true
    }
  }, [metric, range, showRangeTabs])

  const chartData = useMemo(
    () => buildChartDomain(series, showRangeTabs ? range : 'all', { dataOnly: !showRangeTabs }),
    [series, range, showRangeTabs],
  )
  const hasValues = chartData.some((point) => point.value != null)
  const valuedCount = chartData.filter((point) => point.value != null).length
  const tickInterval = tickIntervalForSpan(chartData.length)
  const sparseHistory = !showRangeTabs && valuedCount <= 1

  const latestValue = series?.latest
    ? series.latest[
        metric === 'sleep'
          ? 'sleep_score'
          : metric === 'rhr'
            ? 'resting_heart_rate'
            : metric === 'avg_hr'
              ? 'avg_heart_rate'
              : metric === 'daily' || metric === 'steps'
                ? 'steps'
                : metric === 'calories'
                  ? 'calories'
                  : metric === 'recovery'
                    ? 'recovery_pct'
                    : metric === 'vo2max' || metric === 'fitness'
                      ? 'vo2max'
                      : metric === 'load' || metric === 'training_load'
                        ? 'load_ratio'
                        : metric
      ]
    : [...chartData].reverse().find((point) => point.value != null)?.value

  async function handleExploreHistory() {
    setBackfilling(true)
    setError('')
    try {
      const data = await backfillMetricHistory(metric, range === '7d' ? '4w' : range)
      setSeries(data)
    } catch (err) {
      setError(err.message || 'Failed to backfill history.')
    } finally {
      setBackfilling(false)
    }
  }

  const secondaryName =
    metric === 'daily' || metric === 'steps' ? 'Calories' : 'Secondary'

  const body = (
    <>
      <PageHeader
        eyebrow={eyebrow}
        title={title}
        subtitle={description}
        actions={
          showRangeTabs ? (
            <div className="flex flex-wrap items-center gap-2">
              <RangeTabs
                value={range}
                onChange={setRange}
                variant={health ? 'health' : 'default'}
              />
              <button
                type="button"
                onClick={handleExploreHistory}
                disabled={backfilling || loading}
                className={`rounded-xl border border-[var(--aal-line)] bg-[var(--aal-card)] px-3 py-2 text-sm font-medium text-[var(--aal-ink)] transition disabled:opacity-60 ${
                  health
                    ? 'hover:border-indigo-300 hover:text-indigo-600 dark:hover:text-indigo-300'
                    : ''
                }`}
              >
                {backfilling ? 'Loading history…' : 'Explore history'}
              </button>
            </div>
          ) : null
        }
      />

      {error && <p className="mb-4 text-sm text-danger-muted">{error}</p>}

      {loading ? (
        <SectionCard>
          <LoadingDots
            label={
              showRangeTabs && ['3m', '6m', '1y', 'all'].includes(range)
                ? `Loading ${range.toUpperCase()} chart…`
                : 'Loading chart…'
            }
          />
        </SectionCard>
      ) : !hasValues ? (
        <EmptyState
          title={`No ${title.toLowerCase()} data yet`}
          description="Connect COROS and sync, or explore history to pull a wider date range."
          actionLabel="Connect COROS"
          actionTo="/connect-coros"
        />
      ) : (
        <div className="space-y-6">
          {health ? (
            <div
              className="relative overflow-hidden rounded-2xl border border-[var(--aal-line)] px-4 py-3.5 sm:px-5 sm:py-4"
            >
              <div
                className="pointer-events-none absolute inset-0"
                style={{
                  background:
                    'radial-gradient(120% 80% at 0% 0%, rgba(55,48,163,0.12), transparent 55%), radial-gradient(90% 70% at 100% 20%, rgba(91,141,239,0.1), transparent 50%), linear-gradient(165deg, var(--aal-card), color-mix(in srgb, #312e81 5%, var(--aal-card)))',
                }}
              />
              <div className="relative grid gap-3 sm:grid-cols-3">
                <StatTile
                  label="Latest"
                  value={formatValue(latestValue, valueDigits, valueSuffix)}
                  subtitle={
                    series?.latest?.hrv_assessment ||
                    series?.latest?.recovery_level ||
                    'Cached series'
                  }
                  accent={colors.primary}
                />
                <StatTile
                  label="Points"
                  value={String(chartData.filter((p) => p.value != null).length)}
                  subtitle={`${chartData[0]?.date || ''} → ${
                    chartData[chartData.length - 1]?.date || ''
                  }`}
                  accent={HEALTH_CHART.primary}
                />
                <StatTile
                  label="Source"
                  value={series?.source === 'backfill' ? 'Live pull' : 'Cache'}
                  subtitle={secondaryLabel || 'Postgres + COROS MCP'}
                  accent={colors.secondary || '#818CF8'}
                />
              </div>
            </div>
          ) : (
            <div className="grid gap-4 sm:grid-cols-3">
              <StatTile
                label="Latest"
                value={formatValue(latestValue, valueDigits, valueSuffix)}
                subtitle={
                  series?.latest?.hrv_assessment ||
                  series?.latest?.recovery_level ||
                  'Cached series'
                }
              />
              <StatTile
                label="Points"
                value={String(chartData.filter((p) => p.value != null).length)}
                subtitle={`${chartData[0]?.date || ''} → ${
                  chartData[chartData.length - 1]?.date || ''
                }`}
              />
              <StatTile
                label="Source"
                value={series?.source === 'backfill' ? 'Live pull' : 'Cache'}
                subtitle={secondaryLabel || 'Postgres + COROS MCP'}
              />
            </div>
          )}

          <SectionCard
            title={`${title} trend`}
            subtitle={
              sparseHistory
                ? 'COROS only provides today’s live snapshot for this metric. Sync daily to build a longer chart.'
                : showRangeTabs
                  ? `Showing ${range.toUpperCase()} window${
                      range === 'all' || range === '1y'
                        ? ' from first collected sample'
                        : ''
                    }.`
                  : 'Showing available COROS history from the latest sync.'
            }
          >
            <div className="h-72 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartData}>
                  <CartesianGrid
                    stroke={health ? HEALTH_CHART.grid : 'var(--aal-line)'}
                    strokeDasharray={health ? '4 6' : '3 3'}
                    vertical={false}
                  />
                  <XAxis
                    dataKey="labelShort"
                    tick={{ fontSize: 11, fill: 'var(--aal-muted)' }}
                    stroke={health ? 'transparent' : 'var(--aal-muted)'}
                    tickLine={false}
                    interval={tickInterval}
                    minTickGap={16}
                  />
                  <YAxis
                    tick={{ fontSize: 12, fill: 'var(--aal-muted)' }}
                    stroke={health ? 'transparent' : 'var(--aal-muted)'}
                    tickLine={false}
                    axisLine={false}
                  />
                  <Tooltip
                    cursor={
                      health
                        ? {
                            stroke: HEALTH_CHART.cursorStroke,
                            strokeWidth: 1,
                            strokeDasharray: '4 4',
                          }
                        : undefined
                    }
                    content={
                      health ? (
                        <HealthTooltip
                          labelFormatter={(_, payload) => payload?.[0]?.payload?.date || _}
                          valueFormatter={(value, name) => [
                            value == null
                              ? '—'
                              : formatValue(
                                  value,
                                  valueDigits,
                                  name === secondaryName && (metric === 'daily' || metric === 'steps')
                                    ? ''
                                    : valueSuffix,
                                ),
                            name,
                          ]}
                        />
                      ) : undefined
                    }
                    labelFormatter={
                      health
                        ? undefined
                        : (_, payload) => payload?.[0]?.payload?.date || _
                    }
                    formatter={
                      health
                        ? undefined
                        : (value, name) => [
                            value == null ? '—' : formatValue(value, valueDigits, valueSuffix),
                            name,
                          ]
                    }
                  />
                  <Line
                    type="monotone"
                    dataKey="value"
                    name={
                      metric === 'daily' || metric === 'steps' ? 'Steps' : title
                    }
                    stroke={colors.primary}
                    strokeWidth={2.5}
                    dot={valuedCount <= 14}
                    connectNulls
                    activeDot={{ r: 5, strokeWidth: 2, stroke: '#fff' }}
                  />
                  {showSecondary && colors.secondary ? (
                    <Line
                      type="monotone"
                      dataKey="secondary"
                      name={secondaryName}
                      stroke={colors.secondary}
                      strokeWidth={2.2}
                      dot={valuedCount <= 14}
                      connectNulls
                      activeDot={{ r: 5, strokeWidth: 2, stroke: '#fff' }}
                    />
                  ) : null}
                </LineChart>
              </ResponsiveContainer>
            </div>
          </SectionCard>
        </div>
      )}

      {!loading && (
        <div className="mt-6">
          <MetricExplainer metric={metric} variant={health ? 'health' : 'default'} />
        </div>
      )}
    </>
  )

  if (bare) return <div className="space-y-6">{body}</div>
  return <AppShell title={title}>{body}</AppShell>
}
