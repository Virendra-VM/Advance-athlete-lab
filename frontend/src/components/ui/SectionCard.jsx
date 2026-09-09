export default function SectionCard({
  id,
  title,
  subtitle,
  actions = null,
  children,
  className = '',
  dense = false,
}) {
  return (
    <section
      id={id}
      className={`scroll-mt-24 rounded-2xl border border-[var(--aal-line)] bg-[var(--aal-card)] shadow-sm ${
        dense ? 'p-4' : 'p-5 sm:p-6'
      } ${className}`}
    >
      {(title || actions) && (
        <div
          className={`flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between ${
            dense ? 'mb-2.5' : 'mb-4 gap-3'
          }`}
        >
          <div>
            {title && (
              <h2
                className={`font-semibold text-[var(--aal-ink)] ${
                  dense ? 'text-base' : 'text-lg'
                }`}
              >
                {title}
              </h2>
            )}
            {subtitle && (
              <p className={`text-[var(--aal-muted)] ${dense ? 'text-xs' : 'mt-0.5 text-sm'}`}>
                {subtitle}
              </p>
            )}
          </div>
          {actions}
        </div>
      )}
      {children}
    </section>
  )
}
