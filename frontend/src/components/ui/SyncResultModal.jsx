import { CheckCircle2, X } from 'lucide-react'

/**
 * Modal shown after a Strava/COROS sync completes.
 * @param {{ open: boolean, onClose: () => void, title?: string, message?: string, details?: string[] }} props
 */
export default function SyncResultModal({ open, onClose, title, message, details = [] }) {
  if (!open) return null

  return (
    <div
      className="fixed inset-0 z-[90] flex items-end justify-center bg-black/45 p-4 sm:items-center"
      onClick={onClose}
      role="presentation"
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="sync-result-title"
        className="w-full max-w-md overflow-hidden rounded-2xl border border-[var(--aal-line)] bg-[var(--aal-card)] shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start gap-3 border-b border-[var(--aal-line)] p-5">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-[var(--aal-accent-soft)] text-sage">
            <CheckCircle2 className="h-5 w-5" />
          </div>
          <div className="min-w-0 flex-1">
            <h2 id="sync-result-title" className="text-lg font-semibold text-[var(--aal-ink)]">
              {title || 'Sync complete'}
            </h2>
            {message ? (
              <p className="mt-1 text-sm leading-relaxed text-[var(--aal-muted)]">{message}</p>
            ) : null}
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-1.5 text-[var(--aal-muted)] hover:bg-[var(--aal-bg)]"
            aria-label="Close"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {details.length > 0 ? (
          <ul className="space-y-2 px-5 py-4">
            {details.map((line) => (
              <li
                key={line}
                className="rounded-xl border border-[var(--aal-line)] bg-[var(--aal-bg)]/60 px-3 py-2.5 text-sm text-[var(--aal-ink)]"
              >
                {line}
              </li>
            ))}
          </ul>
        ) : null}

        <div className="flex justify-end border-t border-[var(--aal-line)] px-5 py-4">
          <button
            type="button"
            onClick={onClose}
            className="rounded-xl bg-sage px-5 py-2.5 text-sm font-semibold text-white"
          >
            Got it
          </button>
        </div>
      </div>
    </div>
  )
}

/** Build a clear sync popup payload from provider status. */
export function buildSyncResult(provider, status = {}) {
  const imported = Number(status.imported ?? 0)
  const skipped = Number(status.skipped ?? 0)
  const errors = Array.isArray(status.errors) ? status.errors : []
  const name = provider === 'strava' ? 'Strava' : 'COROS'
  const hasNew = imported > 0

  if (provider === 'strava') {
    if (hasNew) {
      return {
        title: 'Strava activities updated',
        message:
          imported === 1
            ? '1 new activity was brought into Advance Athlete Lab. You can open it from Activities or Schedule.'
            : `${imported} new activities were brought into Advance Athlete Lab. They are ready to view in Activities and Schedule.`,
        details: [
          `${imported} new activit${imported === 1 ? 'y' : 'ies'} imported`,
          skipped > 0
            ? `${skipped} already in your library (skipped)`
            : 'No duplicates to skip',
        ],
      }
    }
    return {
      title: 'Strava is up to date',
      message:
        'We checked Strava and found no new activities since your last sync. Everything in your library is current.',
      details: skipped > 0 ? [`Checked ${skipped} existing activit${skipped === 1 ? 'y' : 'ies'}`] : [],
    }
  }

  // COROS
  if (hasNew) {
    return {
      title: 'COROS data updated',
      message:
        'Fresh health metrics, workouts, and schedule items from COROS are now in Advance Athlete Lab. Dashboard and Schedule reflect the latest sync.',
      details: [
        `${imported} new item${imported === 1 ? '' : 's'} synced`,
        skipped > 0 ? `${skipped} already up to date` : null,
        errors.length ? `${errors.length} warning${errors.length === 1 ? '' : 's'} during sync` : null,
      ].filter(Boolean),
    }
  }
  return {
    title: `${name} is up to date`,
    message:
      'We checked COROS and nothing new needed importing. Your sleep, recovery, activities, and schedule already match the latest data.',
    details: skipped > 0 ? [`${skipped} item${skipped === 1 ? '' : 's'} already current`] : [],
  }
}
