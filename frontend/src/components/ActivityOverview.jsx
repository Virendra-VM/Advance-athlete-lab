import { useMemo, useState } from 'react'
import { computeActivityOverview } from '../utils/activityStats'
import { collectSportOptions, filterOverviewActivities } from '../utils/activityFilters'
import { OverviewFilterBar } from './ActivityFilterBar'
import Card from './ui/Card'
import MetricCard from './ui/MetricCard'
import SportBadge from './SportBadge'

export default function ActivityOverview({ activities }) {
  const [period, setPeriod] = useState('all')
  const [sport, setSport] = useState('All sports')

  const sportOptions = useMemo(() => collectSportOptions(activities), [activities])
  const filteredActivities = useMemo(
    () => filterOverviewActivities(activities, { period, sport }),
    [activities, period, sport],
  )
  const overview = computeActivityOverview(filteredActivities)

  return (
    <section className="space-y-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h2 className="text-2xl font-bold text-slate-900 dark:text-white">Activity Overview</h2>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
            {filteredActivities.length} activities in view
          </p>
        </div>
        <OverviewFilterBar
          period={period}
          sport={sport}
          sportOptions={sportOptions}
          onPeriodChange={setPeriod}
          onSportChange={setSport}
        />
      </div>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard label="Total Activities" value={overview.totalActivities} subtitle="Filtered workouts" />
        <MetricCard label="Total Distance" value={`${overview.totalDistanceKm} km`} subtitle="Filtered volume" />
        <MetricCard label="Moving Time" value={overview.totalMovingHours} subtitle="Total time active" />
        <MetricCard
          label="Avg Heart Rate"
          value={overview.avgHeartRate ? `${overview.avgHeartRate} bpm` : '—'}
          subtitle={overview.maxHeartRate ? `Peak ${overview.maxHeartRate} bpm` : 'No HR data'}
        />
        <MetricCard label="This Week" value={overview.activitiesThisWeek} subtitle="Activities in last 7 days" />
        <MetricCard
          label="Top Sport"
          value={overview.topSport}
          subtitle={overview.topSportCount ? `${overview.topSportCount} sessions` : 'No data'}
        />
        <MetricCard label="Longest Workout" value={`${overview.longestDistanceKm} km`} subtitle="Single activity best" />
        <MetricCard
          label="Sport Mix"
          value={`${overview.sportBreakdown.length}`}
          subtitle="Different activity types"
        />
      </div>

      {overview.sportBreakdown.length > 0 && (
        <Card className="p-6">
          <h3 className="text-lg font-semibold text-slate-900 dark:text-white">Sport Breakdown</h3>
          <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {overview.sportBreakdown.map(({ sport: sportLabel, count }) => (
              <div
                key={sportLabel}
                className="flex items-center justify-between rounded-xl border border-slate-100 bg-slate-50 px-4 py-3 dark:border-white/10 dark:bg-gray-900/50"
              >
                <SportBadge sportType={sportLabel} />
                <span className="text-lg font-bold text-slate-900 dark:text-white">{count}</span>
              </div>
            ))}
          </div>
        </Card>
      )}
    </section>
  )
}
