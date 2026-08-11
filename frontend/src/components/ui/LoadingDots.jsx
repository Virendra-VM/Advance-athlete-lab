export default function LoadingDots({ label = 'Loading', className = '' }) {
  return (
    <div
      className={`flex flex-col items-center justify-center gap-3 py-10 text-sm text-[var(--aal-muted)] ${className}`}
      role="status"
      aria-live="polite"
    >
      <div className="loading-dots" aria-hidden="true">
        <span />
        <span />
        <span />
      </div>
      {label && <p>{label}</p>}
    </div>
  )
}
