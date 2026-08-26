import { Link } from 'react-router-dom'
import { ArrowLeft, ChevronLeft, ChevronRight } from 'lucide-react'
import {
  formatClockTime,
  formatDateLong,
  formatDuration,
} from '../../utils/formatters'
import { getActivityTitle } from '../../utils/sportTypes'
import SportBadge from '../SportBadge'
import { Stat } from './detailShared'

export default function ActivityDetailChrome({
  activity,
  siblings,
  siblingIndex,
  onOlder,
  onNewer,
  heroStats = [],
  heroPrimary,
  children,
  enrichMessage,
}) {
  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <Link
          to="/activities"
          className="inline-flex items-center gap-2 text-sm text-[var(--aal-muted)] hover:text-sage"
        >
          <ArrowLeft className="h-4 w-4" /> All activities
        </Link>
        <div className="flex items-center gap-2">
          <button
            type="button"
            disabled={siblingIndex < 0 || siblingIndex >= siblings.length - 1}
            onClick={onOlder}
            className="rounded-lg border border-[var(--aal-line)] p-2 disabled:opacity-40"
            title="Older activity"
          >
            <ChevronLeft className="h-4 w-4" />
          </button>
          <button
            type="button"
            disabled={siblingIndex <= 0}
            onClick={onNewer}
            className="rounded-lg border border-[var(--aal-line)] p-2 disabled:opacity-40"
            title="Newer activity"
          >
            <ChevronRight className="h-4 w-4" />
          </button>
        </div>
      </div>

      <div className="space-y-4">
        <section className="rounded-2xl border border-[var(--aal-line)] bg-[var(--aal-card)] p-5">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <SportBadge sportType={activity.sport_type} />
              <h1 className="mt-2 text-2xl font-bold sm:text-3xl">{getActivityTitle(activity)}</h1>
              <p className="mt-1 text-sm text-[var(--aal-muted)]">
                {formatDateLong(activity.activity_date)} · {formatClockTime(activity.activity_date)}
                {activity.provider ? ` · ${String(activity.provider).toUpperCase()}` : ''}
                {activity.detail?.sources?.length
                  ? ` · detail ${activity.detail.sources.map((s) => s.toUpperCase()).join('+')}`
                  : ''}
              </p>
              {enrichMessage ? (
                <p className="mt-1 text-xs text-[var(--aal-muted)]">{enrichMessage}</p>
              ) : null}
            </div>
            <div className="text-right">
              {heroPrimary}
              <p className="mt-1 text-xl font-semibold tabular-nums text-[var(--aal-muted)]">
                {formatDuration(activity.moving_time_s)}
                <span className="ml-1 text-xs font-medium">moving</span>
              </p>
            </div>
          </div>

          {heroStats.length ? (
            <div className="mt-5 grid gap-4 border-t border-[var(--aal-line)] pt-4 sm:grid-cols-2 lg:grid-cols-4">
              {heroStats.map((stat) => (
                <Stat key={stat.label} {...stat} />
              ))}
            </div>
          ) : null}
        </section>

        {children}
      </div>
    </div>
  )
}
