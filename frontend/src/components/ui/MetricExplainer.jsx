import { useEffect, useId, useState } from 'react'
import { X } from 'lucide-react'
import { guideForMetric } from '../../utils/metricGuides'

export default function MetricExplainer({ metric }) {
  const guide = guideForMetric(metric)
  const [open, setOpen] = useState(false)
  const titleId = useId()

  useEffect(() => {
    if (!open) return undefined
    function onKey(event) {
      if (event.key === 'Escape') setOpen(false)
    }
    document.addEventListener('keydown', onKey)
    const previous = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', onKey)
      document.body.style.overflow = previous
    }
  }, [open])

  if (!guide) return null

  return (
    <>
      <div className="rounded-2xl border border-[var(--aal-line)] bg-[var(--aal-card)] px-5 py-4">
        <p className="text-sm leading-relaxed text-[var(--aal-muted)]">{guide.summary}</p>
        <button
          type="button"
          onClick={() => setOpen(true)}
          className="mt-3 text-sm font-semibold text-sage hover:underline"
        >
          Read more
        </button>
      </div>

      {open && (
        <div
          className="fixed inset-0 z-[80] flex items-end justify-center bg-black/45 p-4 sm:items-center"
          onClick={() => setOpen(false)}
          role="presentation"
        >
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby={titleId}
            className="max-h-[85vh] w-full max-w-lg overflow-y-auto rounded-2xl border border-[var(--aal-line)] bg-[var(--aal-card)] p-6 shadow-xl"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="mb-4 flex items-start justify-between gap-3">
              <div>
                <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-sage">
                  About this metric
                </p>
                <h2 id={titleId} className="mt-1 text-2xl font-bold text-[var(--aal-ink)]">
                  {guide.title}
                </h2>
              </div>
              <button
                type="button"
                onClick={() => setOpen(false)}
                className="rounded-lg border border-[var(--aal-line)] p-2 text-[var(--aal-muted)]"
                aria-label="Close"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            <p className="text-sm leading-relaxed text-[var(--aal-muted)]">{guide.summary}</p>
            <div className="mt-5 space-y-4">
              {guide.sections.map((section) => (
                <div key={section.heading}>
                  <h3 className="text-sm font-semibold text-[var(--aal-ink)]">{section.heading}</h3>
                  <p className="mt-1 text-sm leading-relaxed text-[var(--aal-muted)]">{section.body}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </>
  )
}
