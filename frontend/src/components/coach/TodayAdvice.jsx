import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { AlertTriangle, MoonStar, RefreshCw, Zap } from 'lucide-react'
import LoadingDots from '../ui/LoadingDots'

const READINESS = {
  proceed: {
    label: 'Green light',
    icon: Zap,
    accent: 'text-sage',
    ring: 'border-sage/35 bg-sage/5',
    panel: 'border-sage/30 bg-[var(--aal-card)]',
  },
  downgrade_to_easy: {
    label: 'Keep it easy',
    icon: MoonStar,
    accent: 'text-amber-status',
    ring: 'border-amber-status/35 bg-amber-50/60 dark:bg-amber-950/20',
    panel: 'border-amber-status/35 bg-[var(--aal-card)]',
  },
  rest_or_mobility: {
    label: 'Rest or mobility',
    icon: MoonStar,
    accent: 'text-danger-muted',
    ring: 'border-red-300/40 bg-red-50/60 dark:bg-red-950/20',
    panel: 'border-red-300/40 bg-[var(--aal-card)]',
  },
}

function formatSleep(min) {
  if (min == null || Number.isNaN(Number(min))) return null
  const hours = Number(min) / 60
  const whole = Math.floor(hours)
  const mins = Math.round((hours - whole) * 60)
  return mins ? `${whole}h ${mins}m` : `${whole}h`
}

function MarkdownInline({ text }) {
  const parts = String(text || '')
    .replace(/\*\*/g, '\u0000')
    .replace(/\u0000([^\u0000]+)\u0000/g, '**$1**')
    .replace(/\u0000/g, '')
    .split(/(\*\*[^*]+\*\*|\[\s*S\d+\s*\])/g)
    .filter((part) => part !== '')
  return parts.map((part, index) => {
    if (part.startsWith('**') && part.endsWith('**') && part.length > 4) {
      return (
        <strong key={index} className="font-semibold text-[var(--aal-ink)]">
          {part.slice(2, -2)}
        </strong>
      )
    }
    if (/^\[\s*S\d+\s*\]$/.test(part)) {
      return (
        <span
          key={index}
          className="ml-0.5 align-super text-[10px] font-medium tracking-wide text-[var(--aal-muted)]"
        >
          {part.replace(/\s/g, '')}
        </span>
      )
    }
    return <span key={index}>{part}</span>
  })
}

function splitKeyedItem(raw) {
  const text = String(raw || '')
    .replace(/^[-•]\s*/, '')
    .replace(/\*\*/g, '')
    .trim()
  const match = text.match(/^([^:]{1,28}):\s+(.*)$/)
  if (match) return { label: match[1].trim(), value: match[2].trim() }
  return { label: null, value: text }
}

export function parseAdviceBrief(text) {
  const raw = String(text || '').trim()
  if (!raw) return { intro: [], sessions: [] }

  const normalized = raw
    .replace(/\r\n/g, '\n')
    .replace(/\s*\*\*\s*(\d+)\.\s*/g, '\n\n$1. ')
    .replace(/(^|\n)\s*\*\*(\d+)\.\s*/g, '$1$2. ')
    .replace(/\s+-\s+\*\*/g, '\n- **')
    .replace(/\s+-\s+(?=[A-Z])/g, '\n- ')
    .replace(/\s+\*\*(Optional add:)\*\*/gi, '\n- **$1**')

  const intro = []
  const sessions = []
  let current = null

  for (const line of normalized.split('\n')) {
    const trimmed = line.trim().replace(/\*\*$/, '').trim()
    if (!trimmed) continue
    const numbered = trimmed.match(/^(\d+)\.\s+(.*)$/)
    if (numbered) {
      current = {
        number: numbered[1],
        title: numbered[2].replace(/\*\*/g, '').trim(),
        items: [],
      }
      sessions.push(current)
      continue
    }
    const bullet = trimmed.match(/^[-•]\s+(.*)$/)
    if (bullet) {
      const item = splitKeyedItem(bullet[1])
      if (current) current.items.push(item)
      else intro.push(item.value)
      continue
    }
    if (current) current.items.push(splitKeyedItem(trimmed))
    else intro.push(trimmed)
  }

  return { intro, sessions }
}

function AdviceBrief({ text, tone = 'sage' }) {
  const { intro, sessions } = parseAdviceBrief(text)
  if (!intro.length && !sessions.length) return null

  const mark =
    tone === 'danger'
      ? 'bg-red-500/15 text-danger-muted'
      : tone === 'amber'
        ? 'bg-amber-500/15 text-amber-status'
        : tone === 'indigo'
          ? 'bg-indigo-500/15 text-indigo-600 dark:text-indigo-300'
          : 'bg-sage/15 text-sage'

  return (
    <div className="mt-3 space-y-3">
      {intro.length ? (
        <p className="text-sm leading-relaxed text-[var(--aal-ink)]/90">
          {intro.map((line, index) => (
            <span key={index}>
              {index > 0 ? ' ' : null}
              <MarkdownInline text={line} />
            </span>
          ))}
        </p>
      ) : null}

      {sessions.length ? (
        <ol className="space-y-2.5">
          {sessions.map((session) => (
            <li
              key={`${session.number}-${session.title}`}
              className="rounded-xl border border-[var(--aal-line)]/90 bg-[var(--aal-bg)]/40 px-3 py-2.5"
            >
              <div className="flex items-start gap-2.5">
                <span
                  className={`mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-[11px] font-bold tabular-nums ${mark}`}
                >
                  {session.number}
                </span>
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-semibold leading-snug text-[var(--aal-ink)]">
                    <MarkdownInline text={session.title} />
                  </p>
                  {session.items.length ? (
                    <ul className="mt-2 space-y-1.5">
                      {session.items
                        .filter((item) => item.label || item.value)
                        .map((item, itemIndex) => (
                        <li
                          key={`${session.number}-${itemIndex}`}
                          className="flex gap-2 text-[13px] leading-snug text-[var(--aal-ink)]/85"
                        >
                          <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-[var(--aal-muted)]" />
                          <span className="min-w-0">
                            {item.label ? (
                              <>
                                <span className="font-semibold text-[var(--aal-ink)]">
                                  {item.label}:
                                </span>{' '}
                                <MarkdownInline text={item.value} />
                              </>
                            ) : (
                              <MarkdownInline text={item.value} />
                            )}
                          </span>
                        </li>
                      ))}
                    </ul>
                  ) : null}
                </div>
              </div>
            </li>
          ))}
        </ol>
      ) : null}
    </div>
  )
}

function AdjustmentNote({ text, title = 'Today’s session' }) {
  if (!text) return null
  const cleaned = String(text).trim()
  const keyed = splitKeyedItem(cleaned)
  return (
    <div className="mt-3 rounded-xl border border-[var(--aal-line)] bg-[var(--aal-card)] px-3 py-2.5">
      <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[var(--aal-muted)]">
        {title}
      </p>
      <p className="mt-1 text-sm leading-relaxed text-[var(--aal-ink)]/90">
        {keyed.label ? (
          <>
            <span className="font-semibold text-[var(--aal-ink)]">{keyed.label}: </span>
            <MarkdownInline text={keyed.value} />
          </>
        ) : (
          <MarkdownInline text={cleaned} />
        )}
      </p>
    </div>
  )
}

function WarningChip({ warning }) {
  const content = (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-[11px] font-semibold ${
        warning.severity === 'critical'
          ? 'bg-red-500/15 text-danger-muted'
          : 'bg-amber-500/15 text-amber-status'
      }`}
    >
      <AlertTriangle className="h-3 w-3 shrink-0" />
      {warning.message}
    </span>
  )
  if (warning.link) {
    return (
      <Link to={warning.link} className="transition hover:opacity-80">
        {content}
      </Link>
    )
  }
  return content
}

function SignalChip({ label, value }) {
  if (value == null || value === '') return null
  return (
    <div className="min-w-[4.5rem] rounded-lg border border-[var(--aal-line)]/80 bg-[var(--aal-card)]/80 px-2.5 py-1.5">
      <p className="text-[10px] font-medium uppercase tracking-[0.12em] text-[var(--aal-muted)]">
        {label}
      </p>
      <p className="mt-0.5 text-sm font-semibold tabular-nums text-[var(--aal-ink)]">{value}</p>
    </div>
  )
}

function CallWarnings({ warnings, label, directive }) {
  if (!warnings?.length && !label && !directive) return null
  return (
    <div className="mt-3 space-y-2 border-t border-[var(--aal-line)]/70 pt-3">
      {label ? (
        <p className="text-xs font-semibold uppercase tracking-[0.14em] text-[var(--aal-muted)]">
          Today&apos;s call · {label}
        </p>
      ) : null}
      {directive ? (
        <p className="text-sm leading-relaxed text-[var(--aal-ink)]/90">{directive}</p>
      ) : null}
      {warnings?.length ? (
        <div className="flex flex-wrap gap-2">
          {warnings.map((warning) => (
            <WarningChip key={warning.code || warning.message} warning={warning} />
          ))}
        </div>
      ) : null}
    </div>
  )
}

const HEALTH_WEEK_TOPICS = new Set(['hrv', 'stress', 'rhr', 'daily', 'sleep'])

const HEALTH_BRIEF = {
  icon: MoonStar,
  accent: 'text-indigo-500 dark:text-indigo-300',
  ring: 'border-indigo-300/40 bg-indigo-50/50 dark:bg-indigo-950/20',
  panel: 'border-indigo-300/35 bg-[var(--aal-card)]',
  button:
    'border-indigo-300/50 bg-indigo-50/80 text-indigo-600 dark:bg-indigo-950/30 dark:text-indigo-300',
}

const WEEK_TOPIC = {
  volume: {
    scopeLabel: 'Volume',
    adjustmentTitle: 'This week’s kilometres',
    refreshTitle: 'Rewrite this volume brief from ACWR, distance, and recovery',
    cacheHeld: 'Held for this week — rewrites if kilometres, ACWR, recovery, or the plan changes.',
    loading: 'Reading this week’s volume…',
  },
  load: {
    scopeLabel: 'Load',
    adjustmentTitle: 'This week’s effort',
    refreshTitle: 'Rewrite this load brief from COROS short/long load and recovery',
    cacheHeld: 'Held for this week — rewrites if the load ratio, recovery, or the plan changes.',
    loading: 'Reading this week’s training load…',
  },
  hrv: {
    scopeLabel: 'HRV',
    adjustmentTitle: 'This week’s HRV',
    refreshTitle: 'Rewrite this brief from overnight HRV only',
    cacheHeld: 'Held for this week — rewrites if overnight HRV changes.',
    loading: 'Reading this week’s HRV…',
  },
  stress: {
    scopeLabel: 'Stress',
    adjustmentTitle: 'This week’s stress',
    refreshTitle: 'Rewrite this brief from daily stress only',
    cacheHeld: 'Held for this week — rewrites if daily stress changes.',
    loading: 'Reading this week’s stress…',
  },
  rhr: {
    scopeLabel: 'Resting HR',
    adjustmentTitle: 'This week’s resting HR',
    refreshTitle: 'Rewrite this brief from overnight resting HR only',
    cacheHeld: 'Held for this week — rewrites if resting HR changes.',
    loading: 'Reading this week’s resting HR…',
  },
  daily: {
    scopeLabel: 'Daily',
    adjustmentTitle: 'This week’s daily health',
    refreshTitle: 'Rewrite this brief from steps, calories, and day-average HR only',
    cacheHeld: 'Held for this week — rewrites if steps, calories, or day-average HR change.',
    loading: 'Reading this week’s daily health…',
  },
  sleep: {
    scopeLabel: 'Sleep',
    adjustmentTitle: 'This week’s sleep',
    refreshTitle: 'Rewrite this brief from overnight sleep only',
    cacheHeld: 'Held for this week — rewrites if sleep duration or stages change.',
    loading: 'Reading this week’s sleep…',
  },
}

export default function TodayAdvice({
  advice,
  loading,
  error,
  onRefresh,
  refreshing,
  compact = false,
  health = null,
  fitness = null,
  load = null,
  loadChips = null,
  scope = 'today',
  topic = null,
  callWarnings = null,
  callLabel = null,
  callDirective = null,
}) {
  const isWeek = scope === 'week'
  const metricOnly = isWeek && HEALTH_WEEK_TOPICS.has(topic)
  const look = metricOnly ? HEALTH_BRIEF : READINESS[advice?.readiness?.action] || READINESS.proceed
  const weekCopy = WEEK_TOPIC[topic] || {
    scopeLabel: 'Week',
    adjustmentTitle: 'This week’s load',
    refreshTitle: 'Rewrite this week’s brief from load and recovery',
    cacheHeld: 'Held for this week — rewrites if load, recovery, or the plan changes.',
    loading: 'Reading this week’s load…',
  }
  const scopeLabel = isWeek ? weekCopy.scopeLabel : 'Today'
  const adjustmentTitle = isWeek ? weekCopy.adjustmentTitle : 'Today’s session'
  const refreshTitle = isWeek
    ? weekCopy.refreshTitle
    : 'Rewrite today’s brief from the latest HRV, recovery, and training'
  const cacheNote = advice?.cached
    ? isWeek
      ? weekCopy.cacheHeld
      : 'Held for today — rewrites if HRV, recovery, health, or training changes.'
    : 'Just updated from your latest signals.'
  if (loading) {
    return (
      <section
        className={`rounded-2xl border border-[var(--aal-line)] bg-[var(--aal-card)] ${
          compact ? 'px-4 py-3' : 'p-5 sm:p-6'
        }`}
      >
        <LoadingDots label={isWeek ? weekCopy.loading : "Reading today's signals…"} />
      </section>
    )
  }

  if (error) {
    return (
      <section
        className={`rounded-2xl border border-[var(--aal-line)] bg-[var(--aal-card)] ${
          compact ? 'px-4 py-3' : 'p-5 sm:p-6'
        }`}
      >
        <p className="text-sm text-danger-muted">{error}</p>
      </section>
    )
  }

  if (!advice) return null

  const readiness = READINESS[advice.readiness?.action] || READINESS.proceed
  const Icon = look.icon
  const body = advice.advice || {}
  const briefTone = metricOnly
    ? 'indigo'
    : advice.readiness?.action === 'rest_or_mobility'
      ? 'danger'
      : advice.readiness?.action === 'downgrade_to_easy'
        ? 'amber'
        : 'sage'

  if (compact) {
    const sleep = formatSleep(health?.sleep_duration_min)
    return (
      <section className={`rounded-2xl border px-4 py-3.5 sm:px-5 ${look.panel}`}>
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div className="flex items-center gap-2">
            <Icon className={`h-4 w-4 shrink-0 ${look.accent}`} />
            <p className={`text-[11px] font-semibold uppercase tracking-[0.16em] ${look.accent}`}>
              {metricOnly ? scopeLabel : `${scopeLabel} · ${readiness.label}`}
            </p>
          </div>
          <button
            type="button"
            onClick={onRefresh}
            disabled={refreshing}
            title={refreshTitle}
            className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--aal-line)] px-2.5 py-1 text-xs font-medium text-[var(--aal-muted)] transition hover:text-[var(--aal-ink)] disabled:opacity-60"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${refreshing ? 'sync-spin' : ''}`} />
            Refresh
          </button>
        </div>

        {body.headline ? (
          <h2 className="mt-2 text-lg font-bold leading-snug text-[var(--aal-ink)] sm:text-xl">
            <MarkdownInline text={body.headline} />
          </h2>
        ) : null}
        <p className="mt-1 text-[11px] text-[var(--aal-muted)]">{cacheNote}</p>
        <AdviceBrief text={body.recommendation} tone={briefTone} />

        <div className="mt-3 flex flex-wrap gap-2">
          {isWeek
            ? (loadChips || []).map((chip) => (
                <SignalChip key={chip.label} label={chip.label} value={chip.value} />
              ))
            : null}
          {isWeek && !metricOnly && (!loadChips || !loadChips.length) ? (
            <>
              <SignalChip
                label="ACWR"
                value={load?.acwr != null ? Number(load.acwr).toFixed(2) : null}
              />
              <SignalChip
                label="7-day"
                value={load?.acuteKm != null ? `${Number(load.acuteKm).toFixed(1)} km` : null}
              />
              <SignalChip
                label="Usual week"
                value={load?.chronicKm != null ? `${Number(load.chronicKm).toFixed(1)} km` : null}
              />
            </>
          ) : null}
          {metricOnly ? null : (
            <>
              <SignalChip
                label="Sleep score"
                value={health?.sleep_score != null ? `${Math.round(health.sleep_score)}` : null}
              />
              <SignalChip label="Time asleep" value={sleep} />
              <SignalChip
                label="HRV"
                value={
                  health?.hrv != null
                    ? `${Math.round(health.hrv)}${health.hrv_assessment ? ` · ${health.hrv_assessment}` : ''}`
                    : null
                }
              />
              <SignalChip
                label="RHR"
                value={health?.resting_heart_rate != null ? `${Math.round(health.resting_heart_rate)}` : null}
              />
              <SignalChip label="Stress" value={health?.stress != null ? `${Math.round(health.stress)}` : null} />
              <SignalChip
                label="Recovery"
                value={
                  fitness?.recovery_pct != null
                    ? `${Math.round(fitness.recovery_pct)}%`
                    : fitness?.recovery_level || null
                }
              />
            </>
          )}
        </div>

        <AdjustmentNote text={body.session_adjustment} title={adjustmentTitle} />

        <CallWarnings warnings={callWarnings} label={callLabel} directive={callDirective} />

        {metricOnly ? null : advice.readiness?.reason ? (
          <p className="mt-2 text-xs text-[var(--aal-muted)]">Why: {advice.readiness.reason}</p>
        ) : null}

        {body.escalate ? (
          <div className="mt-3 flex gap-2 rounded-xl border border-red-300/50 bg-red-50/80 px-3 py-2 text-sm dark:bg-red-950/30">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-danger-muted" />
            <p>
              <span className="font-semibold">See a professional. </span>
              {body.escalation_reason ||
              (metricOnly
                ? 'These readings need a professional look.'
                : 'Your symptoms need assessment before more training.')}
            </p>
          </div>
        ) : null}
      </section>
    )
  }

  const padding = 'p-5 sm:p-6'

  return (
    <section className={`rounded-2xl border ${padding} ${look.ring}`}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-center gap-2">
          <Icon className={`h-4 w-4 ${look.accent}`} />
          <p className={`text-[11px] font-semibold uppercase tracking-[0.18em] ${look.accent}`}>
            {metricOnly ? scopeLabel : `${scopeLabel} · ${readiness.label}`}
          </p>
        </div>
        <button
          type="button"
          onClick={onRefresh}
          disabled={refreshing}
          className="inline-flex items-center gap-2 rounded-lg border border-[var(--aal-line)] px-3 py-1.5 text-xs font-medium text-[var(--aal-muted)] transition hover:text-[var(--aal-ink)] disabled:opacity-60"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${refreshing ? 'sync-spin' : ''}`} />
          Refresh
        </button>
      </div>
      <p className="mt-1 text-[11px] text-[var(--aal-muted)]">{cacheNote}</p>

      <h2
        className={`mt-2 font-bold leading-tight text-[var(--aal-ink)] ${
          compact ? 'text-lg sm:text-xl' : 'text-2xl sm:text-3xl'
        }`}
      >
        <MarkdownInline text={body.headline} />
      </h2>
      <AdviceBrief text={body.recommendation} tone={briefTone} />

      <AdjustmentNote text={body.session_adjustment} title={adjustmentTitle} />

      <CallWarnings warnings={callWarnings} label={callLabel} directive={callDirective} />

      {compact ? null : body.rationale ? (
        <p className="mt-3 text-sm text-[var(--aal-muted)]">
          <MarkdownInline text={body.rationale} />
        </p>
      ) : null}

      {metricOnly ? null : advice.readiness?.reason ? (
        <p className="mt-2 text-xs text-[var(--aal-muted)]">Signal: {advice.readiness.reason}</p>
      ) : null}

      {body.escalate ? (
        <div className="mt-4 flex gap-3 rounded-xl border border-red-300/50 bg-red-50/80 px-3 py-3 text-sm dark:bg-red-950/30">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-danger-muted" />
          <p>
            <span className="font-semibold">See a professional. </span>
            {body.escalation_reason ||
              (metricOnly
                ? 'These readings need a professional look.'
                : 'Your symptoms need assessment before more training.')}
          </p>
        </div>
      ) : null}
    </section>
  )
}

export function TodayAlertButton({
  advice,
  loading,
  error,
  onRefresh,
  refreshing,
  health,
  fitness,
  load = null,
  loadChips = null,
  scope = 'today',
  topic = null,
  callWarnings = null,
  callLabel = null,
  callDirective = null,
}) {
  const [open, setOpen] = useState(false)
  const rootRef = useRef(null)
  const isWeek = scope === 'week'
  const metricOnly = isWeek && HEALTH_WEEK_TOPICS.has(topic)
  const readiness = READINESS[advice?.readiness?.action] || READINESS.proceed
  const look = metricOnly ? HEALTH_BRIEF : readiness
  const Icon = look.icon
  const escalate = Boolean(advice?.advice?.escalate)
  const scopeLabel = isWeek ? (WEEK_TOPIC[topic]?.scopeLabel || 'Week') : 'Today'

  useEffect(() => {
    if (!open) return undefined
    function onPointer(event) {
      if (!rootRef.current?.contains(event.target)) setOpen(false)
    }
    function onKey(event) {
      if (event.key === 'Escape') setOpen(false)
    }
    document.addEventListener('mousedown', onPointer)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onPointer)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  const tone = escalate
    ? 'border-red-300/50 bg-red-50 text-danger-muted dark:bg-red-950/40'
    : metricOnly
      ? HEALTH_BRIEF.button
      : advice?.readiness?.action === 'downgrade_to_easy'
        ? 'border-amber-status/40 bg-amber-50/80 text-amber-status dark:bg-amber-950/30'
        : advice?.readiness?.action === 'rest_or_mobility'
          ? 'border-red-300/40 bg-red-50/70 text-danger-muted dark:bg-red-950/30'
          : 'border-sage/35 bg-sage/10 text-sage'

  return (
    <div ref={rootRef} className="relative">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        className={`inline-flex items-center gap-2 rounded-xl border px-3 py-2 text-sm font-semibold transition ${tone}`}
      >
        {loading && !advice ? (
          <RefreshCw className="h-4 w-4 sync-spin" />
        ) : (
          <Icon className="h-4 w-4" />
        )}
        <span className="hidden sm:inline">
          {metricOnly ? scopeLabel : `${scopeLabel} · ${readiness.label}`}
        </span>
        <span className="sm:hidden">{scopeLabel}</span>
        {escalate ? <span className="h-1.5 w-1.5 rounded-full bg-danger-muted" /> : null}
      </button>

      {open ? (
        <div className="absolute right-0 z-40 mt-2 w-[min(28rem,calc(100vw-1.5rem))] overflow-hidden rounded-2xl border border-[var(--aal-line)] bg-[var(--aal-card)] shadow-xl">
          <div className="max-h-[min(70vh,32rem)] overflow-y-auto bg-[var(--aal-card)]">
            <TodayAdvice
              advice={advice}
              loading={loading}
              error={error}
              onRefresh={onRefresh}
              refreshing={refreshing}
              compact
              health={health}
              fitness={fitness}
              load={load}
              loadChips={loadChips}
              scope={scope}
              topic={topic}
              callWarnings={callWarnings}
              callLabel={callLabel}
              callDirective={callDirective}
            />
          </div>
        </div>
      ) : null}
    </div>
  )
}

export function WeekAlertButton(props) {
  return <TodayAlertButton {...props} scope="week" />
}
