import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ChevronLeft, ChevronRight, Info, Search } from 'lucide-react'
import { listActivities } from '../api/activities'
import { formatDate, formatDistanceKm, formatDuration } from '../utils/formatters'
import ScrollableTable, { stickyTheadClass } from './ui/ScrollableTable'
import { ACTIVITY_RANGE_OPTIONS } from '../utils/activityRanges'

function dateForTab(tabId) {
  const now = new Date()
  if (tabId === 'all') return { from: null, to: null }
  const to = now.toISOString().slice(0, 10)
  const start = new Date(now)
  if (tabId === 'week') start.setDate(start.getDate() - 7)
  if (tabId === 'month') start.setMonth(start.getMonth() - 1)
  if (tabId === 'year') start.setFullYear(start.getFullYear() - 1)
  return { from: start.toISOString().slice(0, 10), to }
}

export default function ActivitiesTable({
  athleteProfileId,
  embedded = false,
  hideToolbar = false,
  initialItems = null,
  range: controlledRange = null,
  onRangeChange = null,
  fill = false,
}) {
  const navigate = useNavigate()
  const [internalRange, setInternalRange] = useState(embedded ? 'all' : 'month')
  const tab = controlledRange ?? internalRange
  const setTab = (next) => {
    setPage(1)
    if (onRangeChange) onRangeChange(next)
    else setInternalRange(next)
  }
  const [q, setQ] = useState('')
  const [provider, setProvider] = useState('')
  const [sport, setSport] = useState('')
  const [showFilters, setShowFilters] = useState(false)
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(embedded ? 5 : 10)
  const [sort, setSort] = useState('date_desc')
  const [data, setData] = useState({ items: initialItems || [], total: initialItems?.length || 0 })
  const [loading, setLoading] = useState(!initialItems)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!athleteProfileId) return
    if (embedded && initialItems && !q && !provider && !sport && page === 1) {
      setData({ items: initialItems, total: initialItems.length })
      setLoading(false)
      return
    }
    let cancelled = false
    async function load() {
      setLoading(true)
      setError('')
      const { from, to } = dateForTab(tab)
      try {
        const result = await listActivities(athleteProfileId, {
          page,
          page_size: pageSize,
          sort,
          q: q || undefined,
          provider: provider || undefined,
          sport: sport || undefined,
          from: from || undefined,
          to: to || undefined,
        })
        if (!cancelled) setData(result)
      } catch (err) {
        if (!cancelled) setError(err.message || 'Failed to load activities.')
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    load()
    return () => {
      cancelled = true
    }
  }, [athleteProfileId, tab, q, provider, sport, page, pageSize, sort, embedded, initialItems])

  const totalPages = Math.max(1, Math.ceil((data.total || 0) / pageSize))
  const pageNumbers = useMemo(() => {
    const maxButtons = 5
    const start = Math.max(1, Math.min(page - 2, totalPages - maxButtons + 1))
    return Array.from({ length: Math.min(maxButtons, totalPages) }, (_, i) => start + i)
  }, [page, totalPages])

  const showInlineRange = !hideToolbar && controlledRange == null && !embedded

  return (
    <div className={fill ? 'flex min-h-0 flex-1 flex-col gap-4 overflow-hidden' : 'space-y-4'}>
      {!hideToolbar && (
        <div className="shrink-0 space-y-4">
          {showInlineRange ? (
            <div className="flex flex-wrap gap-2">
              {ACTIVITY_RANGE_OPTIONS.map((preset) => (
                <button
                  key={preset.id}
                  type="button"
                  onClick={() => setTab(preset.id)}
                  className={`inline-flex h-9 min-w-[5.75rem] items-center justify-center rounded-xl border px-3 text-sm font-medium ${
                    tab === preset.id
                      ? 'border-[var(--aal-link)] text-[var(--aal-link)]'
                      : 'border-[var(--aal-line)] text-[var(--aal-muted)]'
                  }`}
                >
                  {preset.label}
                </button>
              ))}
            </div>
          ) : null}

          <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
            <div className="relative min-h-10 flex-1">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--aal-muted)]" />
              <input
                value={q}
                onChange={(e) => {
                  setQ(e.target.value)
                  setPage(1)
                }}
                placeholder="Search"
                className="h-10 w-full rounded-xl border border-[var(--aal-line)] bg-[var(--aal-card)] py-0 pl-9 pr-3 text-sm outline-none focus:border-sage"
              />
            </div>
            <button
              type="button"
              onClick={() => setShowFilters((v) => !v)}
              className={`inline-flex h-10 min-w-[6.5rem] items-center justify-center rounded-xl border px-4 text-sm font-medium ${
                showFilters
                  ? 'border-sage bg-sage/10 text-sage'
                  : 'border-[var(--aal-line)] text-[var(--aal-ink)]'
              }`}
            >
              Filters
            </button>
          </div>

          {showFilters && (
            <div className="grid gap-3 rounded-xl border border-[var(--aal-line)] bg-[var(--aal-card)] p-4 sm:grid-cols-3">
              <label className="text-sm">
                <span className="mb-1 block text-[var(--aal-muted)]">Provider</span>
                <select
                  value={provider}
                  onChange={(e) => {
                    setProvider(e.target.value)
                    setPage(1)
                  }}
                  className="h-10 w-full rounded-lg border border-[var(--aal-line)] bg-transparent px-3"
                >
                  <option value="">All</option>
                  <option value="strava">Strava</option>
                  <option value="coros">COROS</option>
                </select>
              </label>
              <label className="text-sm">
                <span className="mb-1 block text-[var(--aal-muted)]">Sport contains</span>
                <input
                  value={sport}
                  onChange={(e) => {
                    setSport(e.target.value)
                    setPage(1)
                  }}
                  className="h-10 w-full rounded-lg border border-[var(--aal-line)] bg-transparent px-3"
                />
              </label>
              <label className="text-sm">
                <span className="mb-1 block text-[var(--aal-muted)]">Sort</span>
                <select
                  value={sort}
                  onChange={(e) => setSort(e.target.value)}
                  className="h-10 w-full rounded-lg border border-[var(--aal-line)] bg-transparent px-3"
                >
                  <option value="date_desc">Date (newest)</option>
                  <option value="date_asc">Date (oldest)</option>
                  <option value="distance_desc">Distance</option>
                  <option value="duration_desc">Duration</option>
                </select>
              </label>
            </div>
          )}
        </div>
      )}

      {error && <p className="shrink-0 text-sm text-danger-muted">{error}</p>}

      <div
        className={
          fill
            ? 'flex min-h-0 flex-1 flex-col overflow-hidden rounded-xl border border-[var(--aal-line)] bg-[var(--aal-card)]'
            : 'overflow-hidden rounded-xl border border-[var(--aal-line)] bg-[var(--aal-card)]'
        }
      >
        <ScrollableTable
          fill={fill}
          autoHeight={!fill && !embedded}
          bottomOffset={embedded ? 24 : 88}
          maxHeightClass="max-h-72"
        >
          <table className="min-w-full text-left text-sm">
            <thead className={stickyTheadClass}>
              <tr>
                <th className="px-4 py-3 font-medium">Date</th>
                <th className="px-4 py-3 font-medium">Name</th>
                <th className="px-4 py-3 font-medium">Sport</th>
                <th className="px-4 py-3 font-medium">Distance</th>
                <th className="px-4 py-3 font-medium">Time</th>
                <th className="px-4 py-3 font-medium">Avg HR</th>
                <th className="px-4 py-3 font-medium">Source</th>
                <th className="px-4 py-3 font-medium" />
              </tr>
            </thead>
            <tbody className="bg-[var(--aal-card)]">
              {loading ? (
                <tr>
                  <td colSpan={8} className="px-4 py-8 text-center text-[var(--aal-muted)]">
                    Loading…
                  </td>
                </tr>
              ) : data.items?.length ? (
                data.items.map((activity) => (
                  <tr
                    key={activity.id}
                    className="border-t border-[var(--aal-line)] hover:bg-slate-50/70 dark:hover:bg-white/5"
                  >
                    <td className="px-4 py-3 whitespace-nowrap">{formatDate(activity.activity_date)}</td>
                    <td className="px-4 py-3">
                      <Link
                        to={`/activities/${activity.id}`}
                        className="font-medium text-[var(--aal-link)] underline-offset-2 hover:underline"
                      >
                        {activity.name}
                      </Link>
                    </td>
                    <td className="px-4 py-3">{activity.sport_type || '—'}</td>
                    <td className="px-4 py-3">{formatDistanceKm(activity.distance_m)}</td>
                    <td className="px-4 py-3">{formatDuration(activity.moving_time_s)}</td>
                    <td className="px-4 py-3">
                      {activity.average_heartrate != null
                        ? `${Math.round(activity.average_heartrate)}`
                        : '—'}
                    </td>
                    <td className="px-4 py-3 capitalize">{activity.provider || 'strava'}</td>
                    <td className="px-4 py-3">
                      <button
                        type="button"
                        onClick={() => navigate(`/activities/${activity.id}`)}
                        className="rounded-full p-1 text-[var(--aal-muted)] hover:bg-[var(--aal-accent-soft)]"
                      >
                        <Info className="h-4 w-4" />
                      </button>
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={8} className="px-4 py-8 text-center text-[var(--aal-muted)]">
                    No activities found.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </ScrollableTable>

        {!embedded && (
          <div className="flex shrink-0 flex-col gap-3 border-t border-[var(--aal-line)] px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-sm font-semibold text-[var(--aal-ink)]">Total: {data.total || 0}</p>
            <div className="flex items-center gap-1">
              <button
                type="button"
                disabled={page <= 1}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                className="rounded-lg p-2 disabled:opacity-40"
              >
                <ChevronLeft className="h-4 w-4" />
              </button>
              {pageNumbers.map((num) => (
                <button
                  key={num}
                  type="button"
                  onClick={() => setPage(num)}
                  className={`min-w-8 rounded-lg px-2 py-1 text-sm font-medium ${
                    num === page
                      ? 'bg-blue-100 text-[var(--aal-link)] dark:bg-blue-950/40'
                      : 'text-[var(--aal-muted)]'
                  }`}
                >
                  {num}
                </button>
              ))}
              <button
                type="button"
                disabled={page >= totalPages}
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                className="rounded-lg p-2 disabled:opacity-40"
              >
                <ChevronRight className="h-4 w-4" />
              </button>
            </div>
            <label className="flex items-center gap-2 text-sm text-[var(--aal-muted)]">
              Show per Page:
              <select
                value={pageSize}
                onChange={(e) => {
                  setPageSize(Number(e.target.value))
                  setPage(1)
                }}
                className="rounded-lg border border-[var(--aal-line)] bg-transparent px-2 py-1"
              >
                {[5, 10, 25].map((size) => (
                  <option key={size} value={size}>
                    {size}
                  </option>
                ))}
              </select>
            </label>
          </div>
        )}
      </div>
    </div>
  )
}
