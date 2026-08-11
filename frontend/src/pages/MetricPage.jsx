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
}) {
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

  const body = (
    <>
      <PageHeader
        eyebrow={eyebrow}
        title={title}
        subtitle={description}
        actions={
          showRangeTabs ? (
            <div className="flex flex-wrap items-center gap-2">
              <RangeTabs value={range} onChange={setRange} />
              <button
                type="button"
                onClick={handleExploreHistory}
                disabled={backfilling || loading}
                className="rounded-xl border border-[var(--aal-line)] px-3 py-2 text-sm font-medium text-[var(--aal-ink)] disabled:opacity-60"
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
                  <CartesianGrid stroke="var(--aal-line)" strokeDasharray="3 3" />
                  <XAxis
                    dataKey="labelShort"
                    tick={{ fontSize: 11 }}
                    stroke="var(--aal-muted)"
                    interval={tickInterval}
                    minTickGap={16}
                  />
                  <YAxis tick={{ fontSize: 12 }} stroke="var(--aal-muted)" />
                  <Tooltip
                    labelFormatter={(_, payload) => payload?.[0]?.payload?.date || _}
                    formatter={(value, name) => [
                      value == null ? '—' : formatValue(value, valueDigits, valueSuffix),
                      name,
                    ]}
                  />
                  <Line
                    type="monotone"
                    dataKey="value"
                    name={title}
                    stroke="#6b9080"
                    strokeWidth={2.5}
                    dot={valuedCount <= 14}
                    connectNulls
                    activeDot={{ r: 4 }}
                  />
                  {showSecondary && (
                    <Line
                      type="monotone"
                      dataKey="secondary"
                      name="Secondary"
                      stroke="#6b9ac4"
                      strokeWidth={2}
                      dot={valuedCount <= 14}
                      connectNulls
                    />
                  )}
                </LineChart>
              </ResponsiveContainer>
            </div>
          </SectionCard>
        </div>
      )}

      {!loading && (
        <div className="mt-6">
          <MetricExplainer metric={metric} />
        </div>
      )}
    </>
  )

  if (bare) return <div className="space-y-6">{body}</div>
  return <AppShell title={title}>{body}</AppShell>
}
