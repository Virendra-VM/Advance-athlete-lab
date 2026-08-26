import { useMemo, useState } from 'react'
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { Clock, Route } from 'lucide-react'
import { useTheme } from '../context/ThemeProvider'
import {
  buildVolumeHistory,
  sumVolumeTotals,
  VOLUME_RANGE_OPTIONS,
} from '../utils/volumeHistory'
import BarActiveGlow from './charts/BarActiveEffects'
import Card from './ui/Card'

function VolumeTooltip({ active, payload, mode, isDark }) {
  if (!active || !payload?.length) return null
  const row = payload[0]?.payload
  if (!row) return null

  return (
    <div
      className="rounded-xl border px-3 py-2 text-xs shadow-lg"
      style={{
        backgroundColor: isDark ? '#1f2937' : '#ffffff',
        borderColor: isDark ? 'rgba(255,255,255,0.1)' : '#e2e8f0',
      }}
    >
      <p className="font-semibold text-slate-700 dark:text-slate-200">{row.label}</p>
      <p className="mt-1 text-slate-600 dark:text-slate-300">
        {mode === 'time'
          ? `${row.total_moving_hours}h moving time`
          : `${row.total_distance_km} km`}
      </p>
      <p className="text-slate-500">{row.activity_count} activities</p>
    </div>
  )
}

export default function WeeklyVolumeChart({ activities = [] }) {
  const { theme } = useTheme()
  const isDark = theme === 'dark'
  const [rangeId, setRangeId] = useState('8w')
  const [mode, setMode] = useState('distance')

  const { buckets, range } = useMemo(
    () => buildVolumeHistory(activities, rangeId),
    [activities, rangeId],
  )

  const dataKey = mode === 'time' ? 'total_moving_hours' : 'total_distance_km'
  const totals = useMemo(() => sumVolumeTotals(buckets, mode), [buckets, mode])
  const maxValue = useMemo(
    () => Math.max(...buckets.map((bucket) => bucket[dataKey] || 0), 1),
    [buckets, dataKey],
  )

  const barColor = isDark ? '#6b9080' : '#10b981'
  const barColorMuted = isDark ? '#4a6358' : '#86efac'
  const currentBarColor = isDark ? '#a7c4b5' : '#059669'

  if (!activities?.length) {
    return (
      <Card className="flex min-h-80 items-center justify-center p-6">
        <p className="text-sm text-slate-500 dark:text-slate-400">No volume data yet.</p>
      </Card>
    )
  }

  const rangeLabel = range.type === 'month' ? 'Monthly' : 'Weekly'
  const title = mode === 'time' ? `${rangeLabel} Time Volume` : `${rangeLabel} Distance Volume`

  return (
    <Card className="h-full p-6">
      <div className="mb-4 flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <h3 className="text-lg font-semibold text-slate-900 dark:text-white">{title}</h3>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
            Total:{' '}
            <span className="font-semibold text-slate-800 dark:text-slate-200">
              {mode === 'time' ? `${totals.total}h` : `${totals.total} km`}
            </span>
            {' · '}
            {totals.activities} activities
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <div className="flex rounded-lg border border-slate-200 p-0.5 dark:border-white/10">
            <button
              type="button"
              onClick={() => setMode('distance')}
              className={`flex items-center gap-1 rounded-md px-2.5 py-1 text-xs font-medium ${
                mode === 'distance'
                  ? 'bg-sage text-white'
                  : 'text-slate-600 dark:text-slate-300'
              }`}
            >
              <Route className="h-3.5 w-3.5" /> Distance
            </button>
            <button
              type="button"
              onClick={() => setMode('time')}
              className={`flex items-center gap-1 rounded-md px-2.5 py-1 text-xs font-medium ${
                mode === 'time'
                  ? 'bg-sage text-white'
                  : 'text-slate-600 dark:text-slate-300'
              }`}
            >
              <Clock className="h-3.5 w-3.5" /> Time
            </button>
          </div>
        </div>
      </div>

      <div className="mb-4 flex flex-wrap gap-1.5">
        {VOLUME_RANGE_OPTIONS.map((option) => (
          <button
            key={option.id}
            type="button"
            onClick={() => setRangeId(option.id)}
            className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${
              rangeId === option.id
                ? 'bg-slate-900 text-white dark:bg-white dark:text-slate-900'
                : 'border border-slate-200 text-slate-600 dark:border-white/10 dark:text-slate-300'
            }`}
          >
            {option.label}
          </button>
        ))}
      </div>

      <div className="h-80">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={buckets} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke={isDark ? '#374151' : '#e2e8f0'} />
            <XAxis
              dataKey="label"
              tick={{ fontSize: 11, fill: isDark ? '#9ca3af' : '#64748b' }}
              axisLine={false}
              tickLine={false}
              interval={buckets.length > 12 ? Math.floor(buckets.length / 8) : 0}
            />
            <YAxis
              tick={{ fontSize: 11, fill: isDark ? '#9ca3af' : '#64748b' }}
              axisLine={false}
              tickLine={false}
              width={42}
              tickFormatter={(value) =>
                mode === 'time' ? `${value}h` : `${value}`
              }
            />
            <Tooltip
              cursor={{ fill: 'transparent' }}
              content={<VolumeTooltip mode={mode} isDark={isDark} />}
            />
            <Bar
              dataKey={dataKey}
              radius={[6, 6, 0, 0]}
              isAnimationActive
              animationDuration={600}
              maxBarSize={buckets.length > 20 ? 18 : 36}
              activeBar={BarActiveGlow}
            >
              {buckets.map((entry) => {
                const value = entry[dataKey] || 0
                const intensity = 0.45 + (value / maxValue) * 0.55
                let fill = entry.isCurrent ? currentBarColor : barColor
                if (!entry.isCurrent && value > 0) {
                  fill = isDark
                    ? `rgba(107, 144, 128, ${intensity})`
                    : `rgba(16, 185, 129, ${intensity})`
                }
                if (value === 0) fill = barColorMuted
                return <Cell key={entry.key} fill={fill} />
              })}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </Card>
  )
}
