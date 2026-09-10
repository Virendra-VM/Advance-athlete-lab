import { CheckCircle2 } from 'lucide-react'
import { missingCompletenessItems, profileCompletenessPercent } from '../../utils/profileView'

/** Compact completeness hint — hidden when profile is complete. */
export default function ProfileCompletenessPanel({ form, onJump }) {
  const missing = missingCompletenessItems(form)
  const percent = profileCompletenessPercent(form)

  if (!missing.length) {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2.5 py-1 text-xs font-semibold text-emerald-700 dark:text-emerald-300">
        <CheckCircle2 className="h-3.5 w-3.5" aria-hidden />
        Complete
      </span>
    )
  }

  const preview = missing.slice(0, 5)
  const extra = missing.length - preview.length

  return (
    <div className="rounded-xl border border-amber-500/25 bg-amber-500/[0.06] px-3 py-2.5">
      <p className="text-xs font-semibold text-[var(--aal-ink)]">
        {percent}% complete · {missing.length} field{missing.length === 1 ? '' : 's'} left
      </p>
      <p className="mt-1 text-xs leading-relaxed text-[var(--aal-muted)]">
        {preview.map((item, index) => (
          <span key={item.key}>
            <button
              type="button"
              onClick={() => onJump(item)}
              className="font-medium text-sage underline decoration-dotted underline-offset-2 hover:text-[var(--aal-ink)]"
            >
              {item.label}
            </button>
            {index < preview.length - 1 ? ', ' : ''}
          </span>
        ))}
        {extra > 0 ? ` +${extra} more` : null}
      </p>
    </div>
  )
}
