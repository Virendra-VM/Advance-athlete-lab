import { useCallback, useEffect, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import {
  addWeekPlanToSchedule,
  applyChatWeek,
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
import { TodayAlertButton } from '../components/coach/TodayAdvice'
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
  const location = useLocation()
  const navigate = useNavigate()
  const [focalActivityId, setFocalActivityId] = useState(location.state?.activityId ?? null)
  const [focalActivityName, setFocalActivityName] = useState(location.state?.activityName ?? null)
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

  useEffect(() => {
    if (!location.state?.activityId) return
    setFocalActivityId(location.state.activityId)
    setFocalActivityName(location.state.activityName || null)
    navigate(location.pathname, { replace: true, state: {} })
  }, [location.pathname, location.state, navigate])

  const loadAdvice = useCallback(async (force = false) => {
    setAdviceLoading(true)
    setAdviceError('')
    try {
      setAdvice(await getDailyAdvice({ refresh: Boolean(force) }))
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

  async function handleApplyChatWeek(message) {
    setPublishing(true)
    setError('')
    try {
      const result = await applyChatWeek({
        messageId: typeof message.id === 'number' ? message.id : null,
        markdown: message.content,
        publish: true,
      })
      setPlan(result)
      setMessages((current) =>
        current.map((item) =>
          item.id === message.id ? { ...item, plan_id: result.plan_id } : item,
        ),
      )
    } catch (err) {
      setError(err.message || 'Could not replace this week on the schedule.')
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
      const result = await sendChatMessage(message, { activityId: focalActivityId })
      setMessages(result.history || [])
      if (result.plan) {
        setPlan(result.plan)
        setStatus((current) => (current ? { ...current, has_active_plan: true } : current))
      }
    } catch (err) {
      setMessages((current) => current.filter((item) => item.id !== optimistic.id))
      setError(err.message || 'Message failed to send.')
    } finally {
      setSending(false)
    }
  }

  const fitness = context?.coros?.fitness

  return (
    <AppShell title="Coach" fill>
      {loading ? (
        <div className="flex min-h-0 flex-1 items-center justify-center">
          <LoadingDots label="Loading your coach…" />
        </div>
      ) : !consented ? (
        <div className="min-h-0 flex-1 overflow-y-auto px-6 py-8">
          <EmptyState
            title="Turn on AI coaching"
            description="We only generate plans and answers once you consent to AI coaching. Your data is never used to train a model."
            actionLabel="Open settings"
            actionTo="/settings#privacy"
          />
        </div>
      ) : (
        <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
          <header className="relative z-20 flex shrink-0 flex-wrap items-center justify-between gap-2 border-b border-[var(--aal-line)] bg-[var(--aal-card)]/85 px-3 py-2 backdrop-blur-sm sm:px-5">
            <div className="min-w-0 pl-10 lg:pl-0">
              <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-sage">Coach</p>
              <p className="truncate text-sm font-semibold text-[var(--aal-ink)]">
                {status?.mode === 'ai' ? status.active_provider : 'Rules coach'}
              </p>
              {status?.active_model ? (
                <p className="truncate text-[11px] text-[var(--aal-muted)]">
                  {status.active_provider} · {status.active_model}
                </p>
              ) : null}
              {status?.ai_debug ? (
                <details className="mt-1 text-[10px] text-[var(--aal-muted)]">
                  <summary className="cursor-pointer select-none">AI debug</summary>
                  <pre className="mt-1 max-w-[min(90vw,28rem)] overflow-x-auto rounded-md bg-[var(--aal-bg)] p-2 font-mono text-[10px] leading-relaxed">
                    {JSON.stringify(status.ai_debug, null, 2)}
                  </pre>
                </details>
              ) : null}
            </div>
            <div className="flex flex-wrap items-center justify-end gap-2">
              <PlanActions
                plan={plan}
                generating={generating}
                publishing={publishing}
                onGenerate={handleGenerate}
                onAddToSchedule={handleAddToSchedule}
                canGenerate={consented}
              />
              <TodayAlertButton
                advice={advice}
                loading={adviceLoading && !advice}
                error={adviceError}
                onRefresh={() => loadAdvice(true)}
                refreshing={adviceLoading}
                health={context?.coros?.latest_health}
                fitness={fitness}
              />
            </div>
          </header>

          {error ? (
            <p className="shrink-0 border-b border-red-200/60 bg-red-50/80 px-4 py-2 text-sm text-danger-muted">
              {error}
            </p>
          ) : null}

          {fitness && !profile?.baseline_confirmed_at ? (
            <div className="flex shrink-0 flex-col gap-2 border-b border-sage/25 bg-sage/5 px-4 py-2.5 sm:flex-row sm:items-center sm:justify-between">
              <p className="text-sm">
                <span className="font-semibold">Confirm your baseline. </span>
                Your device estimates{' '}
                {fitness.vo2max != null ? `VO₂max ${Math.round(fitness.vo2max)}` : 'your fitness'}
                {fitness.threshold_pace ? ` · threshold ${fitness.threshold_pace}` : ''}.
              </p>
              <button
                type="button"
                onClick={handleConfirmBaseline}
                disabled={confirmingBaseline}
                className="shrink-0 rounded-xl bg-sage px-3 py-1.5 text-sm font-semibold text-white disabled:opacity-60"
              >
                {confirmingBaseline ? 'Saving…' : 'Confirm baseline'}
              </button>
            </div>
          ) : null}

          <div className="min-h-0 flex-1">
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
              focalLabel={focalActivityName}
              onApplyWeek={handleApplyChatWeek}
              applyingWeek={publishing}
              onAddToSchedule={handleAddToSchedule}
            />
          </div>
        </div>
      )}
    </AppShell>
  )
}
