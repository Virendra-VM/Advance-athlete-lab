import { Link } from 'react-router-dom'

export default function StatTile({
  label,
  value,
  subtitle,
  to = null,
  tone = 'default',
}) {
  const toneClass =
    tone === 'good'
      ? 'border-sage/30 bg-sage/5'
      : tone === 'warn'
        ? 'border-amber-status/30 bg-amber-50/60 dark:bg-amber-950/20'
        : tone === 'bad'
          ? 'border-danger-muted/30 bg-red-50/60 dark:bg-red-950/20'
          : 'border-[var(--aal-line)] bg-[var(--aal-card)]'

  const content = (
    <>
      <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-[var(--aal-muted)]">
        {label}
      </p>
      <p className="mt-2 text-3xl font-bold tracking-tight text-[var(--aal-ink)]">{value}</p>
      {subtitle && <p className="mt-1 text-sm text-[var(--aal-muted)]">{subtitle}</p>}
    </>
  )

  const className = `block rounded-2xl border p-5 transition hover:border-sage/40 ${toneClass}`

  if (to) {
    return (
      <Link to={to} className={className}>
        {content}
      </Link>
    )
  }

  return <div className={className}>{content}</div>
}
