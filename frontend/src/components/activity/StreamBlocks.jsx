import { useMemo, useState } from 'react'
import {
  Area,
  AreaChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import LoadingDots from '../ui/LoadingDots'

function formatElapsedTick(seconds) {
  const total = Math.max(0, Math.floor(Number(seconds) || 0))
  const h = Math.floor(total / 3600)
  const m = Math.floor((total % 3600) / 60)
  const s = total % 60
  if (h > 0) return `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
  return `${m}:${String(s).padStart(2, '0')}`
}

function formatDistanceTick(meters) {
  if (meters == null) return '—'
  const km = Number(meters) / 1000
  if (km >= 10) return `${km.toFixed(0)}`
  if (km >= 1) return `${km.toFixed(1)}`
  return `${km.toFixed(2)}`
}

function elevationDomain(data, dataKey = 'altitude_m') {
  const values = (data || [])
    .map((row) => row?.[dataKey])
    .filter((v) => v != null && !Number.isNaN(Number(v)))
    .map(Number)
  if (!values.length) return ['auto', 'auto']
  const min = Math.min(...values)
  const max = Math.max(...values)
  const span = Math.max(max - min, 8)
  // Strava-like tight padding: ~5–10 m below the lowest point (not from 0).
  const padBelow = span < 40 ? 5 : 10
  const padAbove = Math.max(5, span * 0.08)
  const floor = Math.floor(min - padBelow)
  const ceiling = Math.ceil(max + padAbove)
  if (ceiling <= floor) return [floor, floor + 20]
  return [floor, ceiling]
}

/** Grade % at each point from adjacent elevation / distance (smoothed). */
function withElevationGrade(data = []) {
  if (!data.length) return data
  const window = 3
  return data.map((row, index) => {
    const left = Math.max(0, index - window)
    const right = Math.min(data.length - 1, index + window)
    const a = data[left]
    const b = data[right]
    const elevA = a?.altitude_m
    const elevB = b?.altitude_m
    if (elevA == null || elevB == null) return { ...row, grade_pct: null }

    let distM = null
    if (a.distance_m != null && b.distance_m != null) {
      distM = Number(b.distance_m) - Number(a.distance_m)
    } else if (a.elapsed_s != null && b.elapsed_s != null) {
      const dt = Number(b.elapsed_s) - Number(a.elapsed_s)
      const speed = row.speed_mps ?? a.speed_mps ?? b.speed_mps
      if (dt > 0 && speed != null && speed > 0.3) distM = speed * dt
    }
    if (distM == null || distM < 1) return { ...row, grade_pct: null }

    let grade = ((Number(elevB) - Number(elevA)) / distM) * 100
    grade = Math.max(-45, Math.min(45, grade))
    return { ...row, grade_pct: grade }
  })
}

function formatGrade(grade) {
  if (grade == null || Number.isNaN(Number(grade))) return '—'
  const value = Number(grade)
  const sign = value > 0 ? '+' : ''
  return `${sign}${value.toFixed(1)}%`
}

function StreamTooltip({ active, payload, label, xMode = 'time' }) {
  if (!active || !payload?.length) return null
  const labelText =
    xMode === 'distance'
      ? `${formatDistanceTick(label)} km`
      : formatElapsedTick(label)
  return (
    <div className="rounded-xl border border-[var(--aal-line)] bg-[var(--aal-card)] px-3 py-2 text-xs shadow-lg">
      <p className="mb-1 font-medium text-[var(--aal-muted)]">
        {xMode === 'distance' ? 'Distance' : 'Time'} = {labelText}
      </p>
      {payload.map((entry) => {
        const digits = entry.dataKey === 'power' || entry.dataKey === 'heart_rate' ? 0 : 1
        const value = entry.value
        if (value == null || Number.isNaN(Number(value))) return null
        return (
          <p key={entry.dataKey} style={{ color: entry.color }} className="font-semibold">
            {entry.name}: {Number(value).toFixed(digits)} {entry.unit || ''}
          </p>
        )
      })}
    </div>
  )
}

function ElevationTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null
  const point = payload[0]?.payload || {}
  const elev = point.altitude_m
  const grade = point.grade_pct
  return (
    <div className="rounded-xl border border-[var(--aal-line)] bg-[var(--aal-card)] px-3 py-2 text-xs shadow-lg">
      <p className="mb-1 font-medium text-[var(--aal-muted)]">t = {formatElapsedTick(label)}</p>
      {elev != null ? (
        <p className="font-semibold text-[#2f9e44]">
          Elevation: {Math.round(Number(elev))} m
        </p>
      ) : null}
      <p
        className="mt-0.5 font-semibold"
        style={{
          color:
            grade == null
              ? 'var(--aal-muted)'
              : grade > 3
                ? '#e03131'
                : grade < -3
                  ? '#1c7ed6'
                  : '#2f9e44',
        }}
      >
        Gradient: {formatGrade(grade)}
      </p>
    </div>
  )
}

export function StreamPanel({
  title,
  unit,
  dataKey,
  color,
  data,
  area = false,
  yDomain = null,
}) {
  if (dataKey === 'altitude_m') {
    return <ElevationStreamPanel data={data} />
  }

  const Chart = area ? AreaChart : LineChart
  const domain = yDomain || ['auto', 'auto']

  return (
    <div className="rounded-xl border border-[var(--aal-line)] bg-[var(--aal-card)] p-3">
      <div className="mb-2 flex items-baseline justify-between">
        <p className="text-sm font-semibold text-[var(--aal-ink)]">{title}</p>
        <p className="text-xs text-[var(--aal-muted)]">Unit: {unit}</p>
      </div>
      <div className="h-36 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <Chart data={data}>
            <CartesianGrid stroke="var(--aal-line)" strokeDasharray="3 3" />
            <XAxis
              dataKey="elapsed_s"
              tickFormatter={formatElapsedTick}
              tick={{ fontSize: 10 }}
              stroke="var(--aal-muted)"
              minTickGap={28}
            />
            <YAxis
              domain={domain}
              allowDataOverflow
              tick={{ fontSize: 10 }}
              stroke="var(--aal-muted)"
              width={42}
              label={{
                value: unit,
                angle: -90,
                position: 'insideLeft',
                style: { fill: 'var(--aal-muted)', fontSize: 10 },
              }}
            />
            <Tooltip content={<StreamTooltip xMode="time" />} />
            {area ? (
              <Area
                type="monotone"
                dataKey={dataKey}
                name={title}
                unit={unit}
                stroke={color}
                fill={color}
                fillOpacity={0.25}
                strokeWidth={2}
                dot={false}
                isAnimationActive={false}
                connectNulls
              />
            ) : (
              <Line
                type="monotone"
                dataKey={dataKey}
                name={title}
                unit={unit}
                stroke={color}
                strokeWidth={2}
                dot={false}
                isAnimationActive={false}
                connectNulls
              />
            )}
          </Chart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}

/** Strava-style elevation profile: tight Y scale, soft green gradient fill, grade on hover. */
export function ElevationStreamPanel({ data = [] }) {
  const graded = useMemo(() => withElevationGrade(data), [data])
  const domain = useMemo(() => elevationDomain(graded), [graded])
  const gradientId = useMemo(
    () => `elev-fill-${Math.abs(hashSeed(graded)).toString(36)}`,
    [graded],
  )

  return (
    <div className="rounded-xl border border-[var(--aal-line)] bg-[var(--aal-card)] p-3">
      <div className="mb-2 flex items-baseline justify-between">
        <p className="text-sm font-semibold text-[var(--aal-ink)]">Elevation</p>
        <p className="text-xs text-[var(--aal-muted)]">Unit: m · hover for gradient</p>
      </div>
      <div className="h-40 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={graded}>
            <defs>
              <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#40c057" stopOpacity={0.55} />
                <stop offset="55%" stopColor="#69db7c" stopOpacity={0.28} />
                <stop offset="100%" stopColor="#d3f9d8" stopOpacity={0.06} />
              </linearGradient>
            </defs>
            <CartesianGrid stroke="var(--aal-line)" strokeDasharray="3 3" vertical={false} />
            <XAxis
              dataKey="elapsed_s"
              tickFormatter={formatElapsedTick}
              tick={{ fontSize: 10 }}
              stroke="var(--aal-muted)"
              minTickGap={28}
            />
            <YAxis
              domain={domain}
              allowDataOverflow
              tick={{ fontSize: 10 }}
              stroke="var(--aal-muted)"
              width={42}
              tickFormatter={(v) => String(Math.round(v))}
              label={{
                value: 'm',
                angle: -90,
                position: 'insideLeft',
                style: { fill: 'var(--aal-muted)', fontSize: 10 },
              }}
            />
            <Tooltip
              content={<ElevationTooltip />}
              cursor={{ stroke: '#2f9e44', strokeWidth: 1, strokeDasharray: '4 4' }}
            />
            <Area
              type="monotone"
              dataKey="altitude_m"
              name="Elevation"
              unit="m"
              stroke="#2f9e44"
              fill={`url(#${gradientId})`}
              strokeWidth={2}
              dot={false}
              activeDot={{
                r: 4,
                fill: '#2f9e44',
                stroke: '#fff',
                strokeWidth: 2,
              }}
              isAnimationActive={false}
              connectNulls
              baseValue={Array.isArray(domain) ? domain[0] : 'dataMin'}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}

function hashSeed(rows) {
  const n = rows?.length || 0
  const first = rows?.[0]?.altitude_m ?? 0
  const last = rows?.[n - 1]?.altitude_m ?? 0
  return Math.round(n * 1000 + first * 10 + last * 10)
}

const COMPARE_METRICS = [
  { id: 'heart_rate', metricKey: 'heart_rate', dataKey: 'heart_rate', label: 'Heart rate', unit: 'bpm', color: '#ef4444' },
  { id: 'speed', metricKey: 'speed_mps', dataKey: 'speed_kmh', label: 'Speed', unit: 'km/h', color: '#10b981' },
  { id: 'elevation', metricKey: 'altitude_m', dataKey: 'altitude_m', label: 'Elevation', unit: 'm', color: '#f59e0b' },
  { id: 'power', metricKey: 'power', dataKey: 'power', label: 'Power', unit: 'W', color: '#8b5cf6' },
  { id: 'cadence', metricKey: 'cadence', dataKey: 'cadence', label: 'Cadence', unit: 'rpm', color: '#d946ef' },
]

function CompareTooltip({ active, payload, label, xMode, series }) {
  if (!active || !payload?.length) return null
  const labelText =
    xMode === 'distance'
      ? `${formatDistanceTick(label)} km`
      : formatElapsedTick(label)
  return (
    <div className="rounded-xl border border-[var(--aal-line)] bg-[var(--aal-card)] px-3 py-2 text-xs shadow-lg">
      <p className="mb-1 font-medium text-[var(--aal-muted)]">
        {xMode === 'distance' ? 'Distance' : 'Time'} = {labelText}
      </p>
      {payload.map((entry) => {
        const meta = series.find((s) => s.normKey === entry.dataKey)
        if (!meta) return null
        const raw = entry.payload?.[meta.rawKey]
        if (raw == null || Number.isNaN(Number(raw))) return null
        const digits = meta.dataKey === 'power' || meta.dataKey === 'heart_rate' ? 0 : 1
        return (
          <p key={meta.id} style={{ color: meta.color }} className="font-semibold">
            {meta.label}: {Number(raw).toFixed(digits)} {meta.unit}
          </p>
        )
      })}
    </div>
  )
}

export function CompareStreamsChart({ metrics = [], chartData = [] }) {
  const available = useMemo(
    () => COMPARE_METRICS.filter((m) => metrics.includes(m.metricKey)),
    [metrics],
  )

  const [selected, setSelected] = useState(['heart_rate', 'elevation', 'speed'])
  const [xMode, setXMode] = useState('time')

  const activeSeries = useMemo(() => {
    const picked = available.filter((m) => selected.includes(m.id))
    if (picked.length) return picked
    return available.slice(0, 2)
  }, [available, selected])

  const ranges = useMemo(() => {
    const map = {}
    for (const series of activeSeries) {
      const values = chartData
        .map((row) => row?.[series.dataKey])
        .filter((v) => v != null && !Number.isNaN(Number(v)))
        .map(Number)
      if (!values.length) {
        map[series.id] = { min: 0, max: 1 }
        continue
      }
      let min = Math.min(...values)
      let max = Math.max(...values)
      if (series.dataKey === 'altitude_m') {
        min = min - (max - min < 40 ? 5 : 10)
        max = max + Math.max(5, (max - min) * 0.08)
      }
      if (max <= min) max = min + 1
      map[series.id] = { min, max }
    }
    return map
  }, [activeSeries, chartData])

  const plotData = useMemo(() => {
    const xKey = xMode === 'distance' ? 'distance_m' : 'elapsed_s'
    return chartData
      .filter((row) => row?.[xKey] != null)
      .map((row) => {
        const point = { x: Number(row[xKey]) }
        for (const series of activeSeries) {
          const raw = row[series.dataKey]
          point[`${series.id}_raw`] = raw
          if (raw == null || Number.isNaN(Number(raw))) {
            point[`${series.id}_n`] = null
            continue
          }
          const { min, max } = ranges[series.id] || { min: 0, max: 1 }
          point[`${series.id}_n`] = ((Number(raw) - min) / (max - min)) * 100
        }
        return point
      })
  }, [chartData, activeSeries, ranges, xMode])

  const hasDistance = chartData.some((row) => row?.distance_m != null && Number(row.distance_m) > 0)

  function toggleMetric(id) {
    if (!available.some((m) => m.id === id)) return
    setSelected((prev) => {
      const current = prev.filter((item) => available.some((m) => m.id === item))
      if (current.includes(id)) {
        if (current.length <= 1) return current
        return current.filter((item) => item !== id)
      }
      return [...current, id]
    })
  }

  if (!available.length) return null

  const seriesWithKeys = activeSeries.map((s) => ({
    ...s,
    normKey: `${s.id}_n`,
    rawKey: `${s.id}_raw`,
  }))

  return (
    <div className="rounded-xl border border-[var(--aal-line)] bg-[var(--aal-card)] p-3">
      <div className="mb-3 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="text-sm font-semibold text-[var(--aal-ink)]">Compare metrics</p>
          <p className="text-xs text-[var(--aal-muted)]">
            Overlay streams on one chart. Values are scaled for comparison; tooltip shows real units.
          </p>
        </div>
        <div className="inline-flex rounded-xl border border-[var(--aal-line)] p-1">
          <button
            type="button"
            onClick={() => setXMode('time')}
            className={`h-8 rounded-lg px-3 text-xs font-medium ${
              xMode === 'time'
                ? 'bg-sage/15 text-sage'
                : 'text-[var(--aal-muted)] hover:text-[var(--aal-ink)]'
            }`}
          >
            Time
          </button>
          <button
            type="button"
            disabled={!hasDistance}
            onClick={() => setXMode('distance')}
            className={`h-8 rounded-lg px-3 text-xs font-medium disabled:opacity-40 ${
              xMode === 'distance'
                ? 'bg-sage/15 text-sage'
                : 'text-[var(--aal-muted)] hover:text-[var(--aal-ink)]'
            }`}
          >
            Distance
          </button>
        </div>
      </div>

      <div className="mb-3 flex flex-wrap gap-2">
        {available.map((metric) => {
          const active = activeSeries.some((s) => s.id === metric.id)
          return (
            <button
              key={metric.id}
              type="button"
              onClick={() => toggleMetric(metric.id)}
              className={`inline-flex h-8 items-center gap-1.5 rounded-lg border px-2.5 text-xs font-medium ${
                active
                  ? 'border-transparent text-white'
                  : 'border-[var(--aal-line)] text-[var(--aal-muted)]'
              }`}
              style={active ? { backgroundColor: metric.color } : undefined}
            >
              <span
                className="h-2 w-2 rounded-full"
                style={{ backgroundColor: active ? '#fff' : metric.color }}
              />
              {metric.label}
            </button>
          )
        })}
      </div>

      <div className="h-56 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={plotData}>
            <CartesianGrid stroke="var(--aal-line)" strokeDasharray="3 3" />
            <XAxis
              dataKey="x"
              tickFormatter={xMode === 'distance' ? formatDistanceTick : formatElapsedTick}
              tick={{ fontSize: 10 }}
              stroke="var(--aal-muted)"
              minTickGap={28}
              label={{
                value: xMode === 'distance' ? 'km' : 'time',
                position: 'insideBottomRight',
                offset: -2,
                style: { fill: 'var(--aal-muted)', fontSize: 10 },
              }}
            />
            <YAxis
              domain={[0, 100]}
              tick={{ fontSize: 10 }}
              stroke="var(--aal-muted)"
              width={28}
              tickFormatter={() => ''}
            />
            <Tooltip
              content={<CompareTooltip xMode={xMode} series={seriesWithKeys} />}
            />
            <Legend
              wrapperStyle={{ fontSize: 12 }}
              formatter={(value) => value}
            />
            {seriesWithKeys.map((series) => (
              <Line
                key={series.id}
                type="monotone"
                dataKey={series.normKey}
                name={`${series.label} (${series.unit})`}
                stroke={series.color}
                strokeWidth={2}
                dot={false}
                isAnimationActive={false}
                connectNulls
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}

export function TimelineStreams({
  metrics = [],
  chartData = [],
  fetchingStreams,
  streamMessage,
  prefer = null,
}) {
  const panels = []
  const order =
    prefer === 'hr'
      ? ['heart_rate', 'power', 'cadence', 'speed_mps', 'altitude_m']
      : prefer === 'power'
        ? ['power', 'heart_rate', 'cadence', 'speed_mps', 'altitude_m']
        : ['power', 'heart_rate', 'cadence', 'speed_mps', 'altitude_m']

  const defs = {
    power: { title: 'Power', unit: 'W', dataKey: 'power', color: '#8b5cf6', area: true },
    heart_rate: { title: 'Heart rate', unit: 'bpm', dataKey: 'heart_rate', color: '#ef4444' },
    cadence: { title: 'Cadence', unit: 'rpm', dataKey: 'cadence', color: '#d946ef' },
    speed_mps: { title: 'Speed', unit: 'km/h', dataKey: 'speed_kmh', color: '#10b981' },
    altitude_m: {
      title: 'Elevation',
      unit: 'm',
      dataKey: 'altitude_m',
      color: '#f59e0b',
      area: true,
    },
  }

  for (const key of order) {
    if (!metrics.includes(key === 'speed_mps' ? 'speed_mps' : key)) continue
    const def = defs[key]
    if (!def) continue
    panels.push(<StreamPanel key={key} {...def} data={chartData} />)
  }

  if (!panels.length) {
    return (
      <div className="rounded-xl border border-dashed border-[var(--aal-line)] p-6 text-sm text-[var(--aal-muted)]">
        {fetchingStreams ? (
          <LoadingDots label="Fetching COROS timeline streams…" />
        ) : (
          <p>No stream data available for this activity yet.</p>
        )}
        {streamMessage ? <p className="mt-2 text-xs">{streamMessage}</p> : null}
      </div>
    )
  }

  return (
    <div className="space-y-3">
      {panels}
      <CompareStreamsChart metrics={metrics} chartData={chartData} />
      {streamMessage ? <p className="text-xs text-[var(--aal-muted)]">{streamMessage}</p> : null}
    </div>
  )
}

export function ActivityDataGrid({ rows }) {
  return (
    <section className="rounded-2xl border border-[var(--aal-line)] bg-[var(--aal-card)] p-5">
      <h2 className="mb-4 text-lg font-semibold">All activity data</h2>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {rows.map(([label, value]) => (
          <div key={label}>
            <p className="text-[10px] font-semibold uppercase tracking-wide text-[var(--aal-muted)]">
              {label}
            </p>
            <p className="mt-1 break-all text-sm">{value ?? '—'}</p>
          </div>
        ))}
      </div>
    </section>
  )
}
