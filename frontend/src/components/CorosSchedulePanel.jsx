import Card from './ui/Card'

function formatDistance(meters) {
  if (meters == null || Number.isNaN(Number(meters))) return null
  const km = Number(meters) / 1000
  return `${km.toFixed(km >= 10 ? 0 : 1)} km`
}

export default function CorosSchedulePanel({ schedule = [] }) {
  return (
    <section className="space-y-4">
      <div>
        <h2 className="text-2xl font-bold text-slate-900 dark:text-white">COROS Schedule</h2>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          Upcoming and recent planned sessions from your COROS calendar.
        </p>
      </div>

      <Card className="divide-y divide-slate-100 p-0 dark:divide-white/10">
        {schedule.length === 0 ? (
          <p className="p-6 text-sm text-slate-500 dark:text-slate-400">
            No COROS schedule items synced yet.
          </p>
        ) : (
          schedule.map((item) => (
            <div
              key={`${item.external_id}-${item.schedule_date}`}
              className="flex flex-col gap-1 px-6 py-4 sm:flex-row sm:items-center sm:justify-between"
            >
              <div>
                <p className="font-semibold text-slate-900 dark:text-white">
                  {item.title || 'Planned workout'}
                </p>
                <p className="text-sm text-slate-500 dark:text-slate-400">
                  {[item.schedule_date, item.sport_type].filter(Boolean).join(' · ')}
                </p>
              </div>
              <p className="text-sm text-slate-600 dark:text-slate-300">
                {[
                  item.duration_min != null ? `${Math.round(item.duration_min)} min` : null,
                  formatDistance(item.distance_m),
                ]
                  .filter(Boolean)
                  .join(' · ') || '—'}
              </p>
            </div>
          ))
        )}
      </Card>
    </section>
  )
}
