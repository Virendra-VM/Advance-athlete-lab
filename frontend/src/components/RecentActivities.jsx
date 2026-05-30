import { Timer, Footprints } from 'lucide-react'
import { formatDate, formatDistanceKm, formatDuration } from '../utils/formatters'
import { getActivitySubtitle, getActivityTitle } from '../utils/sportTypes'
import Card from './ui/Card'
import SportBadge from './SportBadge'

export default function RecentActivities({ activities }) {
  if (!activities?.length) {
    return (
      <Card className="p-6">
        <h3 className="text-lg font-semibold text-slate-900 dark:text-white">Recent Activities</h3>
        <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">No activities imported yet.</p>
      </Card>
    )
  }

  return (
    <Card className="p-6">
      <h3 className="text-lg font-semibold text-slate-900 dark:text-white">Recent Activities</h3>
      <ul className="mt-4 divide-y divide-slate-100 dark:divide-white/10">
        {activities.map((activity) => {
          const subtitle = getActivitySubtitle(activity)
          return (
            <li
              key={activity.id}
              className="flex flex-col gap-3 py-4 first:pt-0 last:pb-0 lg:flex-row lg:items-center lg:justify-between"
            >
              <div className="flex items-start gap-3">
                <SportBadge sportType={activity.sport_type} />
                <div>
                  <p className="font-medium text-slate-900 dark:text-white">
                    {getActivityTitle(activity)}
                  </p>
                  {subtitle && (
                    <p className="mt-0.5 text-sm text-slate-500 dark:text-slate-400">{subtitle}</p>
                  )}
                  <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
                    {formatDate(activity.activity_date)}
                  </p>
                </div>
              </div>
              <div className="flex gap-6 text-sm text-slate-600 dark:text-slate-300">
                <span className="flex items-center gap-1.5">
                  <Footprints className="h-4 w-4 text-sage" />
                  {formatDistanceKm(activity.distance_m)}
                </span>
                <span className="flex items-center gap-1.5">
                  <Timer className="h-4 w-4 text-recovery" />
                  {formatDuration(activity.moving_time_s)}
                </span>
              </div>
            </li>
          )
        })}
      </ul>
    </Card>
  )
}
