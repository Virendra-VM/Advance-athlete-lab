import { PRIORITY_GUIDES, formatSeasonDate } from '../../utils/seasonGuides'
import SeasonBaselineCard from './SeasonBaselineCard'

/**
 * Secondary context: upcoming races + how the plan was sized.
 */
export default function SeasonSupportingPanel({ events = [], baseline }) {
  const hasEvents = events.length > 0
  const hasBaseline = Boolean(baseline)

  if (!hasEvents && !hasBaseline) return null

  return (
    <div className="grid gap-4 md:grid-cols-2">
      {hasEvents ? (
        <div className="rounded-2xl border border-[var(--aal-line)] bg-[var(--aal-card)] p-4">
          <h3 className="text-base font-semibold text-[var(--aal-ink)]">Upcoming races</h3>
          <p className="mt-0.5 text-xs text-[var(--aal-muted)]">
            How each event is treated in your plan
          </p>
          <ul className="mt-3 space-y-2">
            {events.map((event) => {
              const priority = PRIORITY_GUIDES[event.priority] || PRIORITY_GUIDES.E
              return (
                <li
                  key={event.id}
                  className={`rounded-xl border px-3 py-2.5 ${priority.accent}`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <p className="font-medium text-[var(--aal-ink)]">
                        <span className="mr-2 text-[10px] font-bold uppercase tracking-wide">
                          {priority.label}
                        </span>
                        {event.name}
                      </p>
                      <p className="mt-0.5 text-xs opacity-80">{priority.meaning}</p>
                    </div>
                    <span className="shrink-0 text-xs font-medium tabular-nums text-[var(--aal-muted)]">
                      {formatSeasonDate(event.date, { withYear: false })}
                    </span>
                  </div>
                </li>
              )
            })}
          </ul>
        </div>
      ) : null}

      {hasBaseline ? (
        <div className="rounded-2xl border border-[var(--aal-line)] bg-[var(--aal-card)] p-4">
          <h3 className="text-base font-semibold text-[var(--aal-ink)]">
            How your plan was sized
          </h3>
          <p className="mt-0.5 text-xs text-[var(--aal-muted)]">
            Limits from your profile, synced activities, and training history
          </p>
          <div className="mt-3">
            <SeasonBaselineCard baseline={baseline} compact />
          </div>
        </div>
      ) : null}
    </div>
  )
}
