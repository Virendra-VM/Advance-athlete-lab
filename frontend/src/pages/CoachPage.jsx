import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { BookOpen, Cpu, ShieldCheck } from 'lucide-react'
import {
  addWeekPlanToSchedule,
  confirmWearableBaseline,
  generateWeekPlan,
  getChatHistory,
  getCoachStatus,
  getDailyAdvice,
  getWeekPlan,
  sendChatMessage,
} from '../api/coach'
import { getCoachContext } from '../api/coros'
import { useAuth } from '../context/AuthContext'
import CoachChat from '../components/coach/CoachChat'
import TodayAdvice from '../components/coach/TodayAdvice'
import { PlanActions } from '../components/coach/WeekPlan'
import AppShell from '../components/layout/AppShell'
import EmptyState from '../components/ui/EmptyState'
import LoadingDots from '../components/ui/LoadingDots'
import { addDaysISO, toISODateLocal } from '../utils/formatters'

function mondayOf(iso) {
  const date = new Date(`${iso}T12:00:00`)
  const weekday = (date.getDay() + 6) % 7
  return addDaysISO(iso, -weekday)
}

export default function CoachPage() {
  const { profile, refreshUser } = useAuth()
  const [status, setStatus] = useState(null)
  const [context, setContext] = useState(null)
  const weekStart = mondayOf(toISODateLocal())
  const [plan, setPlan] = useState(null)
  const [advice, setAdvice] = useState(null)
  const [messages, setMessages] = useState([])
  const [loading, setLoading] = useState(true)
  const [adviceLoading, setAdviceLoading] = useState(false)
  const [generating, setGenerating] = useState(false)
  const [publishing, setPublishing] = useState(false)
  const [sending, setSending] = useState(false)
  const [confirmingBaseline, setConfirmingBaseline] = useState(false)
  const [error, setError] = useState('')
  const [adviceError, setAdviceError] = useState('')

  const consented = Boolean(status?.ai_consent)

  const loadAdvice = useCallback(async () => {
    setAdviceLoading(true)
    setAdviceError('')
    try {
      setAdvice(await getDailyAdvice())
    } catch (err) {
      setAdviceError(err.message || 'Could not load today’s advice.')
    } finally {
      setAdviceLoading(false)
    }
  }, [])

  useEffect(() => {
    let cancelled = false
    async function boot() {
      setLoading(true)
      setError('')
      try {
        const [statusResult, contextResult] = await Promise.all([
          getCoachStatus(),
          getCoachContext().catch(() => null),
        ])
        if (cancelled) return
        setStatus(statusResult)
        setContext(contextResult)
        if (statusResult.ai_consent) {
          const [planResult, historyResult] = await Promise.all([
            getWeekPlan(weekStart).catch(() => null),
            getChatHistory().catch(() => ({ messages: [] })),
          ])
          if (cancelled) return
          setPlan(planResult)
          setMessages(historyResult?.messages || [])
          loadAdvice()
        }
      } catch (err) {
        if (!cancelled) setError(err.message || 'Could not load the coach.')
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    boot()
    return () => {
      cancelled = true
    }
    // Local Monday is computed on each render; boot once after consent.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loadAdvice])

  async function handleGenerate() {
    setGenerating(true)
    setError('')
    try {
      setPlan(await generateWeekPlan(weekStart))
      setStatus((current) => (current ? { ...current, has_active_plan: true } : current))
    } catch (err) {
      setError(err.message || 'Plan generation failed.')
    } finally {
      setGenerating(false)
    }
  }

  async function handleAddToSchedule() {
    if (!plan?.plan_id) return
    setPublishing(true)
    setError('')
    try {
      setPlan(await addWeekPlanToSchedule(plan.plan_id))
    } catch (err) {
      setError(err.message || 'Could not add this week to the schedule.')
    } finally {
      setPublishing(false)
    }
  }

  async function handleConfirmBaseline() {
    setConfirmingBaseline(true)
    try {
      setContext(await confirmWearableBaseline())
      await refreshUser()
    } catch (err) {
      setError(err.message || 'Could not confirm your baseline.')
    } finally {
      setConfirmingBaseline(false)
    }
  }

  async function handleSend(message) {
    setSending(true)
    setError('')
    const optimistic = {
      id: `pending-${Date.now()}`,
      role: 'user',
      content: message,
      created_at: new Date().toISOString(),
    }
    setMessages((current) => [...current, optimistic])
    try {
      const result = await sendChatMessage(message)
      setMessages(result.history || [])
    } catch (err) {
      setMessages((current) => current.filter((item) => item.id !== optimistic.id))
      setError(err.message || 'Message failed to send.')
    } finally {
      setSending(false)
    }
  }

  const flags = context?.readiness_flags || []
  const safety = context?.safety
  const fitness = context?.coros?.fitness
  const modeLabel =
    status?.mode === 'ai'
      ? `AI coach · ${status.active_provider}`
      : 'Rules-based coach (no AI provider configured)'

  return (
    <AppShell title="Coach" fill>
      <div className="mb-2 flex shrink-0 items-end justify-between gap-3">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-sage">Coach</p>
          <h1 className="text-xl font-bold tracking-tight text-[var(--aal-ink)]">This week</h1>
        </div>
        <div className="flex flex-wrap items-center justify-end gap-2 text-xs">
          <span className="inline-flex items-center gap-1.5 rounded-xl border border-[var(--aal-line)] px-2.5 py-1 text-[var(--aal-muted)]">
            <Cpu className="h-3.5 w-3.5" />
            {modeLabel}
          </span>
          {status?.science_chunks ? (
            <span className="hidden items-center gap-1.5 rounded-xl border border-[var(--aal-line)] px-2.5 py-1 text-[var(--aal-muted)] sm:inline-flex">
              <BookOpen className="h-3.5 w-3.5" />
              {status.science_chunks} evidence
            </span>
          ) : null}
        </div>
      </div>

      {error ? <p className="mb-3 shrink-0 text-sm text-danger-muted">{error}</p> : null}

      {loading ? (
        <div className="min-h-0 flex-1 overflow-y-auto">
          <LoadingDots label="Loading your coach…" />
        </div>
      ) : !consented ? (
        <div className="min-h-0 flex-1 overflow-y-auto">
          <EmptyState
            title="Turn on AI coaching"
            description="We only generate plans and answers once you consent to AI coaching. Your data is never used to train a model."
            actionLabel="Open settings"
            actionTo="/settings#privacy"
          />
        </div>
      ) : (
        <div className="flex min-h-0 flex-1 flex-col gap-2 overflow-y-auto overscroll-contain">
          {fitness && !profile?.baseline_confirmed_at ? (
            <div className="flex shrink-0 flex-col gap-3 rounded-2xl border border-sage/35 bg-sage/5 px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
              <p className="text-sm">
                <span className="font-semibold">Confirm your baseline. </span>
                Your device estimates{' '}
                {fitness.vo2max != null ? `VO₂max ${Math.round(fitness.vo2max)}` : 'your fitness'}
                {fitness.threshold_pace ? ` · threshold ${fitness.threshold_pace}` : ''}. Confirming
                lets the coach plan from measured fitness instead of your self-assessment.
              </p>
              <button
                type="button"
                onClick={handleConfirmBaseline}
                disabled={confirmingBaseline}
                className="shrink-0 rounded-xl bg-sage px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-60"
              >
                {confirmingBaseline ? 'Saving…' : 'Confirm baseline'}
              </button>
            </div>
          ) : null}

          <div className="shrink-0">
            <TodayAdvice
              advice={advice}
              loading={adviceLoading && !advice}
              error={adviceError}
              onRefresh={loadAdvice}
              refreshing={adviceLoading}
              compact
              health={context?.coros?.latest_health}
              fitness={context?.coros?.fitness}
            />
          </div>

          {safety?.injuries?.active?.length ? (
            <p className="flex shrink-0 items-start gap-2 text-xs text-[var(--aal-muted)]">
              <ShieldCheck className="mt-0.5 h-3.5 w-3.5 shrink-0 text-sage" />
              <span>
                Planning around {safety.injuries.active.join(', ')}.{' '}
                <Link to="/profile#health" className="underline decoration-dotted">
                  Update
                </Link>
              </span>
            </p>
          ) : null}

          <div className="flex shrink-0 flex-wrap items-center justify-between gap-2">
            <PlanActions
              plan={plan}
              generating={generating}
              publishing={publishing}
              onGenerate={handleGenerate}
              onAddToSchedule={handleAddToSchedule}
              canGenerate={consented}
            />
            {safety ? (
              <p className="text-[11px] text-[var(--aal-muted)]">
                Cap {safety.max_weekly_minutes} min · {safety.max_days_per_week} days ·{' '}
                {safety.max_hard_sessions} hard
                {safety?.load?.acute_minutes != null
                  ? ` · last 7d ${safety.load.acute_minutes} min`
                  : ''}
                {flags.length ? ` · ${flags.join(', ').replaceAll('_', ' ')}` : ''}
              </p>
            ) : null}
          </div>

          <div className="h-[calc(100svh-15.25rem)] min-h-[28rem] w-full shrink-0 lg:h-[calc(100svh-12.5rem)]">
            <CoachChat
              messages={messages}
              onSend={handleSend}
              sending={sending}
              disabled={!consented}
              disabledReason="Enable AI coaching consent to chat."
              plan={plan}
              weekStart={weekStart}
              generating={generating}
              profileId={profile?.id}
            />
          </div>
        </div>
      )}
    </AppShell>
  )
}
