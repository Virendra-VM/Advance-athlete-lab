export default function PageHeader({
  title,
  subtitle,
  actions = null,
  eyebrow = null,
  className = '',
}) {
  return (
    <div
      className={`mb-6 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between ${className}`.trim()}
    >
      <div>
        {eyebrow && (
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-sage">{eyebrow}</p>
        )}
        <h1 className="mt-1 text-2xl font-bold tracking-tight text-[var(--aal-ink)] sm:text-3xl">
          {title}
        </h1>
        {subtitle && <p className="mt-1 text-sm text-[var(--aal-muted)]">{subtitle}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  )
}
