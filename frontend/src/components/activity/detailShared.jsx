export function Stat({ label, value, unit, hint }) {
  return (
    <div className="min-w-0">
      <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[var(--aal-muted)]">
        {label}
      </p>
      <p className="mt-0.5 truncate text-lg font-bold tabular-nums text-[var(--aal-ink)] sm:text-xl">
        {value}
        {unit ? (
          <span className="ml-1 text-xs font-medium text-[var(--aal-muted)]">{unit}</span>
        ) : null}
      </p>
      {hint ? <p className="text-[11px] text-[var(--aal-muted)]">{hint}</p> : null}
    </div>
  )
}

export function DetailTabs({ tabs, active, onChange }) {
  return (
    <div className="flex flex-wrap gap-1 rounded-xl border border-[var(--aal-line)] bg-[var(--aal-card)] p-1">
      {tabs.map((item) => (
        <button
          key={item.id}
          type="button"
          onClick={() => onChange(item.id)}
          className={`inline-flex h-9 min-w-[4.75rem] items-center justify-center rounded-lg px-4 text-sm font-medium ${
            active === item.id
              ? 'bg-sage/15 text-sage'
              : 'text-[var(--aal-muted)] hover:text-[var(--aal-ink)]'
          }`}
        >
          {item.label}
        </button>
      ))}
    </div>
  )
}

export function EmptyDetailState({ title, body }) {
  return (
    <div className="rounded-xl border border-dashed border-[var(--aal-line)] p-6 text-sm text-[var(--aal-muted)]">
      <p className="font-medium text-[var(--aal-ink)]">{title}</p>
      {body ? <p className="mt-1">{body}</p> : null}
    </div>
  )
}
