import { useEffect, useId, useMemo } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import {
  AlertTriangle,
  BookOpen,
  CheckCircle2,
  Info,
  Loader2,
  ShieldAlert,
  X,
} from 'lucide-react'
const SEVERITY_STYLES = {
  critical: {
    icon: ShieldAlert,
    chip: 'bg-red-500/15 text-red-700 dark:text-red-300',
    border: 'border-red-500/30',
  },
  warning: {
    icon: AlertTriangle,
    chip: 'bg-amber-500/15 text-amber-800 dark:text-amber-200',
    border: 'border-amber-500/30',
  },
  info: {
    icon: Info,
    chip: 'bg-indigo-500/10 text-indigo-700 dark:text-indigo-300',
    border: 'border-indigo-500/25',
  },
}

const STATUS_STYLES = {
  green: {
    icon: CheckCircle2,
    label: 'Structurally sound',
    ring: 'border-emerald-500/30 bg-emerald-500/10 text-emerald-800 dark:text-emerald-200',
  },
  amber: {
    icon: AlertTriangle,
    label: 'Review recommended',
    ring: 'border-amber-500/35 bg-amber-500/10 text-amber-900 dark:text-amber-100',
  },
  red: {
    icon: ShieldAlert,
    label: 'Correct before loading',
    ring: 'border-red-500/35 bg-red-500/10 text-red-900 dark:text-red-100',
  },
}

const DOMAIN_STATUS = {
  green: 'bg-emerald-500/15 text-emerald-800 dark:text-emerald-200',
  amber: 'bg-amber-500/15 text-amber-900 dark:text-amber-100',
  red: 'bg-red-500/15 text-red-800 dark:text-red-200',
}

const CATEGORY_LABELS = {
  periodization: 'Periodization',
  load_management: 'Load & recovery',
  race_calendar: 'Race calendar',
  athlete_readiness: 'Readiness',
  general: 'General',
}

function DomainChip({ domain }) {
  return (
    <div
      className={`rounded-xl border border-[var(--aal-line)] px-3 py-2 ${DOMAIN_STATUS[domain.status] || DOMAIN_STATUS.green}`}
    >
      <p className="text-[10px] font-semibold uppercase tracking-[0.12em] opacity-80">
        {domain.label}
      </p>
      <p className="mt-0.5 text-xs font-medium">
        {domain.flag_count
          ? `${domain.flag_count} flag${domain.flag_count === 1 ? '' : 's'}`
          : 'Clear'}
      </p>
    </div>
  )
}

function FlagRow({ flag, onAction }) {
  const style = SEVERITY_STYLES[flag.severity] || SEVERITY_STYLES.info
  const Icon = style.icon

  return (
    <li className={`rounded-xl border px-3 py-3 ${style.border} bg-[var(--aal-card)]`}>
      <div className="flex items-start gap-2.5">
        <Icon className="mt-0.5 h-4 w-4 shrink-0 opacity-90" />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <p className="text-sm font-semibold text-[var(--aal-ink)]">{flag.title}</p>
            <span
              className={`rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide ${style.chip}`}
            >
              {flag.severity}
            </span>
            {flag.category ? (
              <span className="rounded-full bg-[var(--aal-bg)] px-2 py-0.5 text-[10px] font-medium text-[var(--aal-muted)]">
                {CATEGORY_LABELS[flag.category] || flag.category}
              </span>
            ) : null}
          </div>
          <p className="mt-1 text-sm leading-snug text-[var(--aal-muted)]">{flag.detail}</p>
          {flag.metric ? (
            <p className="mt-2 inline-flex flex-wrap items-center gap-2 rounded-lg bg-[var(--aal-bg)]/60 px-2 py-1 text-[11px] text-[var(--aal-ink)]">
              <span className="font-semibold">{flag.metric.label}:</span>
              <span className="tabular-nums">{flag.metric.value}</span>
              {flag.metric.reference ? (
                <span className="text-[var(--aal-muted)]">· ref {flag.metric.reference}</span>
              ) : null}
            </p>
          ) : null}
          {flag.evidence ? (
            <p className="mt-2 flex items-start gap-1.5 text-[11px] leading-relaxed text-[var(--aal-muted)]">
              <BookOpen className="mt-0.5 h-3 w-3 shrink-0 text-indigo-500" />
              <span>{flag.evidence}</span>
            </p>
          ) : null}
          {flag.action !== 'none' && flag.action_label && onAction ? (
            <button
              type="button"
              onClick={() => onAction(flag.action)}
              className="mt-2 text-xs font-semibold text-indigo-600 transition hover:text-indigo-500 dark:text-indigo-300"
            >
              {flag.action_label} →
            </button>
          ) : null}
        </div>
      </div>
    </li>
  )
}

export default function SeasonAuditModal({
  open,
  audit,
  loading = false,
  error = '',
  onClose,
  onAction,
}) {
  const titleId = useId()

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

  const status = audit?.summary?.status || 'green'
  const statusStyle = STATUS_STYLES[status] || STATUS_STYLES.green
  const StatusIcon = statusStyle.icon

  const groupedFlags = useMemo(() => {
    const groups = {}
    for (const flag of audit?.flags || []) {
      const key = flag.category || 'general'
      groups[key] = groups[key] || []
      groups[key].push(flag)
    }
    return groups
  }, [audit?.flags])

  return (
    <AnimatePresence>
      {open ? (
        <motion.div
          className="fixed inset-0 z-[90] flex items-end justify-center bg-black/50 p-4 sm:items-center"
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
            className="flex max-h-[90vh] w-full max-w-2xl flex-col overflow-hidden rounded-2xl border border-[var(--aal-line)] bg-[var(--aal-card)] shadow-xl"
            onClick={(event) => event.stopPropagation()}
            initial={{ opacity: 0, y: 24, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 16, scale: 0.98 }}
          >
            <div className="flex items-start justify-between gap-3 border-b border-[var(--aal-line)] px-5 py-4">
              <div>
                <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-indigo-500 dark:text-indigo-300">
                  Evidence-based review
                </p>
                <h2 id={titleId} className="text-lg font-bold text-[var(--aal-ink)]">
                  Season periodization audit
                </h2>
                <p className="mt-0.5 text-xs text-[var(--aal-muted)]">
                  Deterministic checks against load-management and block-periodization heuristics
                </p>
              </div>
              <button
                type="button"
                onClick={onClose}
                aria-label="Close"
                className="shrink-0 rounded-lg border border-[var(--aal-line)] p-1.5 text-[var(--aal-muted)] transition hover:text-[var(--aal-ink)]"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4">
              {loading ? (
                <div className="flex items-center justify-center gap-2 py-12 text-sm text-[var(--aal-muted)]">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Running audit…
                </div>
              ) : error ? (
                <p className="py-8 text-sm text-danger-muted">{error}</p>
              ) : audit ? (
                <div className="space-y-4">
                  <div className={`rounded-xl border px-4 py-3 ${statusStyle.ring}`}>
                    <div className="flex items-start gap-2.5">
                      <StatusIcon className="mt-0.5 h-5 w-5 shrink-0" />
                      <div>
                        <p className="text-xs font-semibold uppercase tracking-[0.14em] opacity-80">
                          {statusStyle.label}
                        </p>
                        <p className="mt-0.5 text-sm font-medium leading-snug">
                          {audit.summary?.headline}
                        </p>
                        <p className="mt-1 text-[11px] text-[var(--aal-muted)]">
                          {audit.summary?.critical_count || 0} critical ·{' '}
                          {audit.summary?.warning_count || 0} warning ·{' '}
                          {audit.summary?.info_count || 0} info
                        </p>
                      </div>
                    </div>
                  </div>

                  {audit.domains?.length ? (
                    <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                      {audit.domains.map((domain) => (
                        <DomainChip key={domain.id} domain={domain} />
                      ))}
                    </div>
                  ) : null}

                  {audit.flags?.length ? (
                    Object.entries(groupedFlags).map(([category, flags]) => (
                      <section key={category}>
                        <h3 className="mb-2 text-[10px] font-semibold uppercase tracking-[0.14em] text-[var(--aal-muted)]">
                          {CATEGORY_LABELS[category] || category}
                        </h3>
                        <ul className="space-y-2">
                          {flags.map((flag) => (
                            <FlagRow
                              key={`${flag.code}-${flag.title}`}
                              flag={flag}
                              onAction={onAction}
                            />
                          ))}
                        </ul>
                      </section>
                    ))
                  ) : (
                    <p className="text-sm text-[var(--aal-muted)]">
                      No flags — macro structure, load profile, and race spacing align with
                      endurance periodization guidelines.
                    </p>
                  )}

                  <p className="border-t border-[var(--aal-line)] pt-3 text-[11px] leading-relaxed text-[var(--aal-muted)]">
                    Not medical advice. Rules derive from ACWR bands, taper meta-analyses, and
                    mesocycle recovery ratios used in the engine — not a pass/fail grade.
                  </p>
                </div>
              ) : null}
            </div>
          </motion.div>
        </motion.div>
      ) : null}
    </AnimatePresence>
  )
}
