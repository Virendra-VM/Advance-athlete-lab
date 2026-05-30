const selectClass =
  'rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-xs text-slate-700 outline-none focus:ring-2 focus:ring-sage dark:border-white/10 dark:bg-gray-900 dark:text-slate-200'

const inputClass =
  'rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-xs text-slate-700 outline-none focus:ring-2 focus:ring-sage dark:border-white/10 dark:bg-gray-900 dark:text-slate-200'

export function OverviewFilterBar({ period, sport, sportOptions, onPeriodChange, onSportChange }) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <select value={period} onChange={(e) => onPeriodChange(e.target.value)} className={selectClass}>
        <option value="all">All time</option>
        <option value="week">This week</option>
        <option value="month">This month</option>
        <option value="90d">Last 90 days</option>
        <option value="year">This year</option>
      </select>
      <select value={sport} onChange={(e) => onSportChange(e.target.value)} className={selectClass}>
        {sportOptions.map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </select>
    </div>
  )
}

export function HistoryFilterBar({
  search,
  sport,
  sportOptions,
  dateFrom,
  dateTo,
  minDistanceKm,
  hasHr,
  sort,
  onSearchChange,
  onSportChange,
  onDateFromChange,
  onDateToChange,
  onMinDistanceChange,
  onHasHrChange,
  onSortChange,
  onClear,
}) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <input
        type="search"
        value={search}
        onChange={(e) => onSearchChange(e.target.value)}
        placeholder="Search activity"
        className={`${inputClass} min-w-[9rem]`}
      />
      <select value={sport} onChange={(e) => onSportChange(e.target.value)} className={selectClass}>
        {sportOptions.map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </select>
      <input
        type="date"
        value={dateFrom}
        onChange={(e) => onDateFromChange(e.target.value)}
        className={inputClass}
        title="From date"
      />
      <input
        type="date"
        value={dateTo}
        onChange={(e) => onDateToChange(e.target.value)}
        className={inputClass}
        title="To date"
      />
      <input
        type="number"
        min="0"
        step="0.1"
        value={minDistanceKm}
        onChange={(e) => onMinDistanceChange(e.target.value)}
        placeholder="Min km"
        className={`${inputClass} w-20`}
      />
      <select value={hasHr} onChange={(e) => onHasHrChange(e.target.value)} className={selectClass}>
        <option value="all">All HR</option>
        <option value="with">With HR</option>
        <option value="without">No HR</option>
      </select>
      <select value={sort} onChange={(e) => onSortChange(e.target.value)} className={selectClass}>
        <option value="date_desc">Newest</option>
        <option value="date_asc">Oldest</option>
        <option value="distance_desc">Longest</option>
        <option value="distance_asc">Shortest</option>
      </select>
      <button
        type="button"
        onClick={onClear}
        className="rounded-lg px-2 py-1.5 text-xs text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200"
      >
        Clear
      </button>
    </div>
  )
}
