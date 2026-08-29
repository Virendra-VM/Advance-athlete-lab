import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import { listActivities } from '../api/activities'
import { getStravaConnectionStatus, getStravaSyncStatus, startStravaSync } from '../api/strava'
import { cardShellClass } from '../utils/statusColors'
import {
  formatDate,
  formatDistanceKm,
  formatDuration,
} from '../utils/formatters'
import { collectSportOptions, filterHistoryActivities } from '../utils/activityFilters'
import { getActivityTitle } from '../utils/sportTypes'
import { HistoryFilterBar } from './ActivityFilterBar'
import Card from './ui/Card'
import ScrollableTable, { stickyTheadClass } from './ui/ScrollableTable'
import SportBadge from './SportBadge'

const PAGE_SIZE = 50

export default function ActivityHistory({ athleteProfileId, refreshKey = 0 }) {
  const navigate = useNavigate()
  const [activities, setActivities] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [page, setPage] = useState(0)
  const [search, setSearch] = useState('')
  const [sport, setSport] = useState('All sports')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [minDistanceKm, setMinDistanceKm] = useState('')
  const [hasHr, setHasHr] = useState('all')
  const [sort, setSort] = useState('date_desc')

  const loadActivities = useCallback(async () => {
    if (!athleteProfileId) return

    setLoading(true)
    setError('')

    try {
      const activityPage = await listActivities(athleteProfileId, {
        page: 1,
        page_size: 500,
      })
      setActivities(activityPage.items || [])
    } catch (err) {
      setError(err.message || 'Failed to load activity history.')
    } finally {
      setLoading(false)
    }
  }, [athleteProfileId])

  useEffect(() => {
    loadActivities()
  }, [loadActivities, refreshKey])

  const sportOptions = useMemo(() => collectSportOptions(activities), [activities])

  const filteredActivities = useMemo(
    () =>
      filterHistoryActivities(activities, {
        search,
        sport,
        dateFrom,
        dateTo,
        minDistanceKm,
        hasHr,
        sort,
      }),
    [activities, search, sport, dateFrom, dateTo, minDistanceKm, hasHr, sort],
  )

  const totalPages = Math.max(1, Math.ceil(filteredActivities.length / PAGE_SIZE))
  const pageItems = filteredActivities.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE)

  useEffect(() => {
    setPage(0)
  }, [search, sport, dateFrom, dateTo, minDistanceKm, hasHr, sort])

  useEffect(() => {
    if (page >= totalPages) setPage(Math.max(0, totalPages - 1))
  }, [page, totalPages])

  function clearFilters() {
    setSearch('')
    setSport('All sports')
    setDateFrom('')
    setDateTo('')
    setMinDistanceKm('')
    setHasHr('all')
    setSort('date_desc')
  }

  async function handleRefresh() {
    setLoading(true)
    setError('')
    try {
      const status = await getStravaConnectionStatus()
      if (status.connected) {
        const syncStatus = await getStravaSyncStatus()
        if (!syncStatus.running) {
          try {
            await startStravaSync()
          } catch (err) {
            if (!String(err.message || '').includes('409')) throw err
          }
        }
        let attempts = 0
        let current = await getStravaSyncStatus()
        while (current.running && attempts < 90) {
          await new Promise((resolve) => setTimeout(resolve, 2000))
          current = await getStravaSyncStatus()
          attempts += 1
        }
        if (current.errors?.length) {
          setError(current.errors[0])
        }
      }
      await loadActivities()
    } catch (err) {
      setError(err.message || 'Failed to refresh activities.')
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <section className={`p-8 text-center text-slate-500 dark:text-slate-400 ${cardShellClass}`}>
        Loading activity history...
      </section>
    )
  }

  if (error) {
    return (
      <section className="rounded-2xl border border-danger-muted/30 bg-red-50 p-6 text-danger-muted dark:bg-red-950/30">
        {error}
      </section>
    )
  }

  if (activities.length === 0) {
    return (
      <section className="rounded-2xl border border-dashed border-slate-200 bg-white p-8 text-center dark:border-white/10 dark:bg-gray-800">
        <h2 className="text-xl font-semibold text-slate-900 dark:text-white">No imported activities yet</h2>
        <p className="mt-2 text-slate-500 dark:text-slate-400">
          Go to{' '}
          <Link to="/settings" className="font-medium text-sage">
            Settings
          </Link>{' '}
          to upload your Strava export or connect Strava.
        </p>
      </section>
    )
  }

  return (
    <section className="space-y-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h2 className="text-2xl font-bold text-slate-900 dark:text-white">Activity History</h2>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
            {filteredActivities.length} of {activities.length} activities
          </p>
        </div>
        <button
          type="button"
          onClick={handleRefresh}
          className="self-start rounded-xl border border-slate-200 bg-white px-4 py-2 text-sm text-slate-600 dark:border-white/10 dark:bg-gray-800 dark:text-slate-300"
        >
          Refresh
        </button>
      </div>

      <HistoryFilterBar
        search={search}
        sport={sport}
        sportOptions={sportOptions}
        dateFrom={dateFrom}
        dateTo={dateTo}
        minDistanceKm={minDistanceKm}
        hasHr={hasHr}
        sort={sort}
        onSearchChange={setSearch}
        onSportChange={setSport}
        onDateFromChange={setDateFrom}
        onDateToChange={setDateTo}
        onMinDistanceChange={setMinDistanceKm}
        onHasHrChange={setHasHr}
        onSortChange={setSort}
        onClear={clearFilters}
      />

      <Card className="overflow-hidden p-0">
        <ScrollableTable autoHeight bottomOffset={72}>
          <table className="min-w-full text-left text-sm">
            <thead
              className={`${stickyTheadClass} border-b border-slate-100 text-xs uppercase tracking-wide dark:border-white/10`}
            >
              <tr>
                <th className="px-4 py-3">Date</th>
                <th className="px-4 py-3">Sport</th>
                <th className="px-4 py-3">Activity</th>
                <th className="px-4 py-3">Distance</th>
                <th className="px-4 py-3">Moving Time</th>
                <th className="px-4 py-3">Avg HR</th>
                <th className="px-4 py-3">Max HR</th>
              </tr>
            </thead>
            <tbody className="bg-[var(--aal-card)]">
              {pageItems.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-4 py-8 text-center text-slate-500">
                    No activities match these filters.
                  </td>
                </tr>
              ) : (
                pageItems.map((activity) => (
                  <tr
                    key={activity.id}
                    onClick={() => navigate(`/activities/${activity.id}`)}
                    className="cursor-pointer border-b border-slate-100 transition-colors hover:bg-slate-50 dark:border-white/10 dark:hover:bg-gray-800/50"
                  >
                    <td className="px-4 py-3 text-slate-600 dark:text-slate-300">
                      {formatDate(activity.activity_date)}
                    </td>
                    <td className="px-4 py-3">
                      <SportBadge sportType={activity.sport_type} />
                    </td>
                    <td className="px-4 py-3 font-medium">
                      <Link
                        to={`/activities/${activity.id}`}
                        className="text-sage hover:underline"
                      >
                        {getActivityTitle(activity)}
                      </Link>
                    </td>
                    <td className="px-4 py-3 text-slate-600 dark:text-slate-300">
                      {formatDistanceKm(activity.distance_m)}
                    </td>
                    <td className="px-4 py-3 text-slate-600 dark:text-slate-300">
                      {formatDuration(activity.moving_time_s)}
                    </td>
                    <td className="px-4 py-3 text-slate-600 dark:text-slate-300">
                      {activity.average_heartrate
                        ? `${Math.round(activity.average_heartrate)} bpm`
                        : '—'}
                    </td>
                    <td className="px-4 py-3 text-slate-600 dark:text-slate-300">
                      {activity.max_heartrate ? `${Math.round(activity.max_heartrate)} bpm` : '—'}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </ScrollableTable>

        <div className="flex items-center justify-between border-t border-slate-100 px-4 py-3 text-sm text-slate-500 dark:border-white/10 dark:text-slate-400">
          <span>
            Showing {filteredActivities.length === 0 ? 0 : page * PAGE_SIZE + 1}–
            {Math.min((page + 1) * PAGE_SIZE, filteredActivities.length)} of {filteredActivities.length}
          </span>
          <div className="flex items-center gap-2">
            <button
              type="button"
              disabled={page === 0}
              onClick={() => setPage((current) => current - 1)}
              className="rounded-lg border border-slate-200 p-1.5 disabled:opacity-40 dark:border-white/10"
            >
              <ChevronLeft className="h-4 w-4" />
            </button>
            <span>
              Page {page + 1} / {totalPages}
            </span>
            <button
              type="button"
              disabled={page >= totalPages - 1}
              onClick={() => setPage((current) => current + 1)}
              className="rounded-lg border border-slate-200 p-1.5 disabled:opacity-40 dark:border-white/10"
            >
              <ChevronRight className="h-4 w-4" />
            </button>
          </div>
        </div>
      </Card>
    </section>
  )
}
