const DEFAULT_OPTIONS = [
  { id: '7d', label: '7D' },
  { id: '4w', label: '4W' },
  { id: '3m', label: '3M' },
  { id: '6m', label: '6M' },
  { id: '1y', label: '1Y' },
  { id: 'all', label: 'All' },
]

export default function RangeTabs({ value, onChange, options = DEFAULT_OPTIONS }) {
  return (
    <div className="inline-flex flex-wrap gap-1 rounded-xl border border-[var(--aal-line)] bg-[var(--aal-card)] p-1">
      {options.map((option) => {
        const active = value === option.id
        return (
          <button
            key={option.id}
            type="button"
            onClick={() => onChange(option.id)}
            className={`rounded-lg px-3 py-1.5 text-sm font-medium transition ${
              active
                ? 'bg-sage/15 text-sage'
                : 'text-[var(--aal-muted)] hover:bg-[var(--aal-accent-soft)] hover:text-[var(--aal-ink)]'
            }`}
          >
            {option.label}
          </button>
        )
      })}
    </div>
  )
}
