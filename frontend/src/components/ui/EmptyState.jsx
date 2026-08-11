import { Link } from 'react-router-dom'

export default function EmptyState({ title, description, actionLabel, actionTo }) {
  return (
    <div className="rounded-2xl border border-dashed border-[var(--aal-line)] bg-[var(--aal-card)] px-6 py-12 text-center">
      <h3 className="text-lg font-semibold text-[var(--aal-ink)]">{title}</h3>
      {description && <p className="mx-auto mt-2 max-w-md text-sm text-[var(--aal-muted)]">{description}</p>}
      {actionLabel && actionTo && (
        <Link
          to={actionTo}
          className="mt-5 inline-flex rounded-xl bg-sage px-4 py-2.5 text-sm font-semibold text-white"
        >
          {actionLabel}
        </Link>
      )}
    </div>
  )
}
