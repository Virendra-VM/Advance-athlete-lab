export default function LoadEquation({
  cells,
  mobileHint,
  acuteKm,
  chronicKm,
  acwr,
}) {
  const resolved =
    cells ||
    [
      {
        hint: 'Acute · last 7 days',
        label: 'This week',
        value: `${Number(acuteKm || 0).toFixed(1)}`,
        unit: 'km',
      },
      {
        hint: 'Chronic · 28 days ÷ 4',
        label: 'Usual week',
        value: `${Number(chronicKm || 0).toFixed(1)}`,
        unit: 'km',
      },
      {
        hint: 'ACWR',
        label: 'Ratio',
        value: acwr == null ? '—' : Number(acwr).toFixed(2),
        unit: '',
      },
    ]

  return (
    <div>
      {mobileHint ? (
        <p className="mb-3 text-center text-xs text-[var(--aal-muted)] sm:hidden">{mobileHint}</p>
      ) : null}
      <div className="grid gap-3 sm:grid-cols-[1fr_auto_1fr_auto_1fr] sm:items-stretch">
        {resolved.map((cell, index) => (
          <div key={cell.label} className="contents">
            <div className="rounded-2xl border border-[var(--aal-line)] bg-[var(--aal-bg)] px-4 py-3">
              <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-sage">{cell.hint}</p>
              <p className="mt-2 font-display text-3xl tabular-nums tracking-tight text-[var(--aal-ink)]">
                {cell.value}
                {cell.unit ? (
                  <span className="ml-1 text-base font-sans font-medium text-[var(--aal-muted)]">
                    {cell.unit}
                  </span>
                ) : null}
              </p>
              <p className="mt-1 text-sm text-[var(--aal-muted)]">{cell.label}</p>
            </div>
            {index === 0 ? (
              <div className="hidden items-center justify-center px-1 text-2xl text-[var(--aal-muted)] sm:flex">
                ÷
              </div>
            ) : null}
            {index === 1 ? (
              <div className="hidden items-center justify-center px-1 text-2xl text-[var(--aal-muted)] sm:flex">
                =
              </div>
            ) : null}
          </div>
        ))}
      </div>
    </div>
  )
}
