export default function SectionCard({ title, subtitle, actions = null, children, className = '' }) {
  return (
    <section
      className={`rounded-2xl border border-[var(--aal-line)] bg-[var(--aal-card)] p-5 shadow-sm sm:p-6 ${className}`}
    >
      {(title || actions) && (
        <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            {title && <h2 className="text-lg font-semibold text-[var(--aal-ink)]">{title}</h2>}
            {subtitle && <p className="mt-0.5 text-sm text-[var(--aal-muted)]">{subtitle}</p>}
          </div>
          {actions}
        </div>
      )}
      {children}
    </section>
  )
}
