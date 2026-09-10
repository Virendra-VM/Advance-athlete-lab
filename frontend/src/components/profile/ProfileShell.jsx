/**
 * Shared profile page frame — full-width spacing for Training & Zones pages.
 */
export default function ProfileShell({
  title,
  subtitle,
  actions = null,
  children,
  className = '',
}) {
  return (
    <div className={`w-full space-y-6 ${className}`}>
      {(title || actions) && (
        <header className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          <div className="min-w-0 flex-1">
            {title ? (
              <h1 className="font-display text-2xl font-medium tracking-tight text-[var(--aal-ink)] sm:text-3xl">
                {title}
              </h1>
            ) : null}
            {subtitle ? (
              <p className="mt-1 text-sm leading-relaxed text-[var(--aal-muted)]">{subtitle}</p>
            ) : null}
          </div>
          {actions ? (
            <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>
          ) : null}
        </header>
      )}

      <div className="space-y-5">{children}</div>
    </div>
  )
}
