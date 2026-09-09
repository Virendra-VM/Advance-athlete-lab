import { useEffect, useId } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { AlertTriangle, CheckCircle2, X } from 'lucide-react'

export default function SeasonFeedbackModal({
  open,
  variant = 'success',
  title,
  message,
  onClose,
}) {
  const titleId = useId()
  const isError = variant === 'error'
  const Icon = isError ? AlertTriangle : CheckCircle2

  useEffect(() => {
    if (!open) return undefined
    function onKey(event) {
      if (event.key === 'Escape') onClose?.()
    }
    document.addEventListener('keydown', onKey)
    const previous = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', onKey)
      document.body.style.overflow = previous
    }
  }, [open, onClose])

  return (
    <AnimatePresence>
      {open ? (
        <motion.div
          className="fixed inset-0 z-[91] flex items-end justify-center bg-black/45 p-4 sm:items-center"
          onClick={onClose}
          role="presentation"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
        >
          <motion.div
            role="dialog"
            aria-modal="true"
            aria-labelledby={titleId}
            className="w-full max-w-md overflow-hidden rounded-2xl border border-[var(--aal-line)] bg-[var(--aal-card)] shadow-xl"
            onClick={(event) => event.stopPropagation()}
            initial={{ opacity: 0, y: 20, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 12, scale: 0.98 }}
          >
            <div className="flex items-start gap-3 px-5 py-4">
              <Icon
                className={`mt-0.5 h-5 w-5 shrink-0 ${
                  isError ? 'text-red-600 dark:text-red-300' : 'text-emerald-600 dark:text-emerald-300'
                }`}
              />
              <div className="min-w-0 flex-1">
                <h2 id={titleId} className="text-base font-bold text-[var(--aal-ink)]">
                  {title}
                </h2>
                {message ? (
                  <p className="mt-1 text-sm leading-relaxed text-[var(--aal-muted)]">{message}</p>
                ) : null}
              </div>
              <button
                type="button"
                onClick={onClose}
                aria-label="Close"
                className="shrink-0 rounded-lg p-1 text-[var(--aal-muted)] transition hover:text-[var(--aal-ink)]"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            <div className="border-t border-[var(--aal-line)] px-5 py-3">
              <button
                type="button"
                onClick={onClose}
                className="w-full rounded-xl border border-[var(--aal-line)] px-4 py-2 text-sm font-semibold text-[var(--aal-ink)] transition hover:border-indigo-300"
              >
                OK
              </button>
            </div>
          </motion.div>
        </motion.div>
      ) : null}
    </AnimatePresence>
  )
}
