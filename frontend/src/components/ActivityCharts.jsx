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
import { useTheme } from '../context/ThemeProvider'
import { formatSportType } from '../utils/sportTypes'
import Card from './ui/Card'

const METRIC_DEFS = [
  { key: 'speed_kmh', label: 'Speed', unit: 'km/h', color: '#10b981', source: 'speed_mps', scale: 3.6 },
  { key: 'pace_min_per_km', label: 'Pace', unit: 'min/km', color: '#6366f1' },
  { key: 'altitude_m', label: 'Elevation', unit: 'm', color: '#f59e0b' },
  { key: 'heart_rate', label: 'Heart Rate', unit: 'bpm', color: '#ef4444' },
  { key: 'cadence', label: 'Cadence', unit: 'rpm', color: '#8b5cf6' },
  { key: 'power', label: 'Power', unit: 'W', color: '#ec4899' },
]

function formatAxisValue(value, xMode) {
  if (xMode === 'time') {
    const minutes = Math.floor(value / 60)
    const seconds = Math.floor(value % 60)
    return `${minutes}:${String(seconds).padStart(2, '0')}`
  }
  return `${(value / 1000).toFixed(1)} km`
}

function isRideSport(sportType) {
  const label = formatSportType(sportType)
  return label === 'Bike' || (sportType || '').toLowerCase().includes('ride')
}

function buildPointValues(point) {
  const values = { ...point }
  if (point.speed_mps != null) {
    values.speed_kmh = point.speed_mps * 3.6
  }
  return values
}

function getElevationDomain(values) {
  const nums = values.filter((v) => v != null)
  if (!nums.length) return ['auto', 'auto']
  const min = Math.min(...nums)
  const max = Math.max(...nums)
  const range = max - min
  const pad = Math.max(8, range * 0.15)
  return [Math.floor(min - pad), Math.ceil(max + pad)]
}

function normalizeValue(value, min, max) {
  if (value == null || max === min) return null
  return ((value - min) / (max - min)) * 100
}

function CustomTooltip({ active, payload, label, xMode, overlayMode, metricDefs }) {
  if (!active || !payload?.length) return null

  return (
    <div className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs shadow-lg dark:border-white/10 dark:bg-gray-900">
      <p className="mb-1 font-medium text-slate-500">
        {xMode === 'time' ? `Time ${formatAxisValue(label, 'time')}` : `Distance ${formatAxisValue(label, 'distance')}`}
      </p>
      {payload.map((entry) => {
        const def = metricDefs.find((m) => m.key === entry.dataKey)
        const raw = entry.payload[`${entry.dataKey}_raw`]
        const display = raw != null ? Number(raw).toFixed(2) : Number(entry.value).toFixed(2)
        return (
          <p key={entry.dataKey} style={{ color: entry.color }} className="font-medium">
            {def?.label}: {display} {def?.unit}
            {overlayMode && entry.payload[`${entry.dataKey}_raw`] != null ? '' : ''}
          </p>
        )
      })}
    </div>
  )
}

export default function ActivityCharts({ points, availableMetrics, sportType }) {
  const { theme } = useTheme()
  const isDark = theme === 'dark'
  const isRide = isRideSport(sportType)

  const visibleMetrics = useMemo(() => {
    let options = METRIC_DEFS.filter((m) => {
      if (m.key === 'speed_kmh') return availableMetrics.includes('speed_mps')
      return availableMetrics.includes(m.key)
    })
    if (isRide) {
      options = options.filter((m) => m.key !== 'pace_min_per_km')
    }
    return options
  }, [availableMetrics, isRide])

  const [selectedMetrics, setSelectedMetrics] = useState([])
  const [xMode, setXMode] = useState('time')

  useEffect(() => {
    if (!visibleMetrics.length) return
    setSelectedMetrics((current) => {
      const valid = current.filter((key) => visibleMetrics.some((m) => m.key === key))
      if (valid.length) return valid
      const preferred = isRide
        ? visibleMetrics.find((m) => m.key === 'speed_kmh')?.key
        : visibleMetrics.find((m) => m.key === 'heart_rate')?.key
      return [preferred || visibleMetrics[0].key]
    })
  }, [visibleMetrics, isRide])

  const activeMetrics = visibleMetrics.filter((m) => selectedMetrics.includes(m.key))

  const xKey = xMode === 'time' ? 'elapsed_s' : 'distance_m'
  const overlayMode = activeMetrics.length > 1

  const enrichedPoints = useMemo(
    () => points.map((point) => buildPointValues(point)),
    [points],
  )

  const metricRanges = useMemo(() => {
    const ranges = {}
    for (const metric of activeMetrics) {
      const values = enrichedPoints
        .map((p) => p[metric.key])
        .filter((v) => v != null)
      if (values.length) {
        ranges[metric.key] = { min: Math.min(...values), max: Math.max(...values) }
      }
    }
    return ranges
  }, [enrichedPoints, activeMetrics])

  const chartData = useMemo(() => {
    return enrichedPoints.map((point) => {
      const row = { x: point[xKey] }
      for (const metric of activeMetrics) {
        const raw = point[metric.key]
        row[`${metric.key}_raw`] = raw
        if (overlayMode) {
          const range = metricRanges[metric.key]
          row[metric.key] =
            range && raw != null ? normalizeValue(raw, range.min, range.max) : null
        } else {
          row[metric.key] = raw
        }
      }
      return row
    })
  }, [enrichedPoints, activeMetrics, xKey, overlayMode, metricRanges])

  function toggleMetric(key) {
    setSelectedMetrics((current) => {
      if (current.includes(key)) {
        return current.length === 1 ? current : current.filter((k) => k !== key)
      }
      return [...current, key]
    })
  }

  if (!points?.length) {
    return (
      <Card className="p-6">
        <p className="text-sm text-slate-500 dark:text-slate-400">No track data available for this activity.</p>
      </Card>
    )
  }

  const yAxisIds = ['left', 'right', 'offset']

  return (
    <Card className="p-6">
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <p className="text-xs text-slate-500 dark:text-slate-400">
          {overlayMode
            ? 'Overlay mode — lines normalized 0–100%, values shown in tooltip'
            : 'Select multiple metrics to overlay on one chart'}
        </p>
        <div className="flex gap-1">
          <button
            type="button"
            onClick={() => setXMode('time')}
            className={`rounded-lg px-2.5 py-1 text-xs ${
              xMode === 'time' ? 'bg-slate-900 text-white dark:bg-white dark:text-slate-900' : 'text-slate-500'
            }`}
          >
            Time
          </button>
          <button
            type="button"
            onClick={() => setXMode('distance')}
            className={`rounded-lg px-2.5 py-1 text-xs ${
              xMode === 'distance'
                ? 'bg-slate-900 text-white dark:bg-white dark:text-slate-900'
                : 'text-slate-500'
            }`}
          >
            Distance
          </button>
        </div>
      </div>

      <div className="mb-4 flex flex-wrap gap-1.5">
        {visibleMetrics.map((option) => {
          const active = activeMetrics.some((m) => m.key === option.key)
          return (
            <button
              key={option.key}
              type="button"
              onClick={() => toggleMetric(option.key)}
              className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${
                active
                  ? 'text-white'
                  : 'border border-slate-200 text-slate-600 dark:border-white/10 dark:text-slate-300'
              }`}
              style={active ? { backgroundColor: option.color } : undefined}
            >
              {option.label}
            </button>
          )
        })}
      </div>

      {overlayMode && (
        <div className="mb-3 flex flex-wrap gap-3 text-xs text-slate-500">
          {activeMetrics.map((metric) => {
            const range = metricRanges[metric.key]
            if (!range) return null
            return (
              <span key={metric.key} className="flex items-center gap-1.5">
                <span className="inline-block h-2 w-2 rounded-full" style={{ backgroundColor: metric.color }} />
                {metric.label}: {range.min.toFixed(1)}–{range.max.toFixed(1)} {metric.unit}
              </span>
            )
          })}
        </div>
      )}

      <div className="h-96">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" stroke={isDark ? '#374151' : '#e2e8f0'} />
            <XAxis
              dataKey="x"
              type="number"
              domain={['dataMin', 'dataMax']}
              tickFormatter={(value) => formatAxisValue(value, xMode)}
              tick={{ fontSize: 11, fill: isDark ? '#9ca3af' : '#64748b' }}
            />

            {overlayMode ? (
              <YAxis
                yAxisId="left"
                domain={[0, 100]}
                tick={{ fontSize: 10, fill: isDark ? '#9ca3af' : '#64748b' }}
                tickFormatter={(v) => `${Math.round(v)}%`}
              />
            ) : (
              activeMetrics.map((metric, index) => {
                const yAxisId = yAxisIds[index] || 'left'
                const isElevation = metric.key === 'altitude_m'
                const domain = isElevation
                  ? getElevationDomain(enrichedPoints.map((p) => p.altitude_m))
                  : ['auto', 'auto']

                return (
                  <YAxis
                    key={metric.key}
                    yAxisId={yAxisId}
                    orientation={index === 0 ? 'left' : 'right'}
                    domain={domain}
                    width={index === 0 ? 52 : 48}
                    tick={{ fontSize: 10, fill: metric.color }}
                    tickFormatter={(v) =>
                      isElevation ? `${Math.round(v)}` : `${Number(v).toFixed(0)}`
                    }
                    axisLine={{ stroke: metric.color }}
                    tickLine={{ stroke: metric.color }}
                    label={
                      index === 0
                        ? { value: metric.unit, angle: -90, position: 'insideLeft', fill: metric.color, fontSize: 10 }
                        : undefined
                    }
                  />
                )
              })
            )}

            <Tooltip
              content={
                <CustomTooltip
                  xMode={xMode}
                  overlayMode={overlayMode}
                  metricDefs={METRIC_DEFS}
                />
              }
            />

            {activeMetrics.map((metric, index) => (
              <Line
                key={metric.key}
                yAxisId={overlayMode ? 'left' : yAxisIds[index] || 'left'}
                type="monotone"
                dataKey={metric.key}
                stroke={metric.color}
                strokeWidth={2}
                dot={false}
                isAnimationActive={false}
                connectNulls
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </Card>
  )
}
