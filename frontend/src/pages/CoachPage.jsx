import { useCallback, useEffect, useRef, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import {
  addWeekPlanToSchedule,
  applyChatWeek,
  confirmWearableBaseline,
  getChatHistory,
  getCoachStatus,
  getDailyAdvice,
  getTodaysCall,
  getWeekPlan,
  getWeekPlanContext,
  sendChatMessage,
} from '../api/coach'
import {
  buildRecoveryShiftMessage,
  buildWeekCommitMessage,
  buildWeekReviewMessage,
} from '../utils/weekPlanFlow'
import { getCoachContext } from '../api/coros'
import { useAuth } from '../context/AuthContext'
import CoachChat from '../components/coach/CoachChat'
import { TodayAlertButton } from '../components/coach/TodayAdvice'
import CyclePhaseChip from '../components/coach/CyclePhaseChip'
import { PlanActions } from '../components/coach/WeekPlan'
import AppShell from '../components/layout/AppShell'
import EmptyState from '../components/ui/EmptyState'
import LoadingDots from '../components/ui/LoadingDots'
import { addDaysISO, toISODateLocal } from '../utils/formatters'
import {
  clearWeekFlowState,
  loadComposerDraft,
  loadComposerStorage,
  saveWeekFlowState,
} from '../utils/coachComposerStorage'

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
  const [todaysCall, setTodaysCall] = useState(null)
  const [messages, setMessages] = useState([])
  const [loading, setLoading] = useState(true)
  const [adviceLoading, setAdviceLoading] = useState(false)
  const [publishing, setPublishing] = useState(false)
  const [sending, setSending] = useState(false)
  const [confirmingBaseline, setConfirmingBaseline] = useState(false)
  const [error, setError] = useState('')
  const [adviceError, setAdviceError] = useState('')
  const [pendingWeekFlow, setPendingWeekFlow] = useState(false)
  const [weekFlowContext, setWeekFlowContext] = useState(null)
  const [weekFlowStep, setWeekFlowStep] = useState(null)
  const [weekConstraints, setWeekConstraints] = useState('')
  const [chatDraft, setChatDraft] = useState('')
  const [draftSeed, setDraftSeed] = useState(null)
  const [recoveryShift, setRecoveryShift] = useState(false)
  const [recoveryPhase, setRecoveryPhase] = useState(null)
  const abortRef = useRef(null)
  const weekFlowRestoreSkipped = useRef(Boolean(location.state?.weekPlanFlow))

  const consented = Boolean(status?.ai_consent)

  useEffect(() => {
    if (!profile?.id || weekFlowRestoreSkipped.current) return undefined
    weekFlowRestoreSkipped.current = true
    const stored = loadComposerStorage(profile.id)
    if (!stored?.weekFlowStep) return undefined
    setWeekFlowStep(stored.weekFlowStep)
    setWeekConstraints(stored.weekConstraints || '')
    setRecoveryShift(Boolean(stored.recoveryShift))
    setRecoveryPhase(stored.recoveryPhase || null)
    let cancelled = false
    getWeekPlanContext()
      .then((ctx) => {
        if (cancelled) return
        setWeekFlowContext(ctx)
        const notes = stored.weekConstraints || ctx?.planning_notes || profile?.planning_notes || ''
        const savedDraft = loadComposerDraft(profile.id)
        if (savedDraft.trim()) return
        let draft
        if (stored.recoveryShift && stored.recoveryPhase) {
          draft = buildRecoveryShiftMessage(stored.recoveryPhase, notes)
        } else if (stored.weekFlowStep === 'commit') {
          draft = buildWeekCommitMessage(ctx, notes)
        } else {
          draft = buildWeekReviewMessage(ctx, notes)
        }
        setChatDraft(draft)
        setDraftSeed(Date.now())
      })
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [profile?.id])

  useEffect(() => {
    if (!profile?.id) return
    saveWeekFlowState(profile.id, {
      weekFlowStep,
      weekConstraints,
      recoveryShift,
      recoveryPhase,
    })
  }, [profile?.id, weekFlowStep, weekConstraints, recoveryShift, recoveryPhase])

  useEffect(() => {
    const state = location.state || {}
    if (state.activityId) {
      setFocalActivityId(state.activityId)
      setFocalActivityName(state.activityName || null)
    }
    if (state.weekPlanFlow) {
      weekFlowRestoreSkipped.current = true
      setPendingWeekFlow(true)
      setRecoveryShift(Boolean(state.recoveryShift))
      setRecoveryPhase(state.recoveryPhase || null)
      setWeekFlowStep('review')
    }
    if (state.activityId || state.weekPlanFlow) {
      navigate(location.pathname, { replace: true, state: {} })
    }
  }, [location.pathname, location.state, navigate])

  useEffect(() => {
    if (!pendingWeekFlow || !consented) return undefined
    let cancelled = false
    async function loadWeekFlowDraft() {
      try {
        const ctx = await getWeekPlanContext()
        if (cancelled) return
        setWeekFlowContext(ctx)
        const notes = ctx?.planning_notes || profile?.planning_notes || ''
        setWeekConstraints(notes)
        const draft = recoveryShift
          ? buildRecoveryShiftMessage(recoveryPhase, notes)
          : buildWeekReviewMessage(ctx, notes)
        setChatDraft(draft)
        setDraftSeed(Date.now())
        setPendingWeekFlow(false)
      } catch (err) {
        if (!cancelled) {
          setError(err.message || 'Could not load season context for this week.')
          setPendingWeekFlow(false)
        }
      }
    }
    loadWeekFlowDraft()
    return () => {
      cancelled = true
    }
  }, [pendingWeekFlow, consented, recoveryShift, recoveryPhase, profile?.planning_notes])

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
          const [planResult, historyResult, callResult] = await Promise.all([
            getWeekPlan(weekStart).catch(() => null),
            getChatHistory().catch(() => ({ messages: [] })),
            getTodaysCall().catch(() => null),
          ])
          if (cancelled) return
          setPlan(planResult)
          setMessages(historyResult?.messages || [])
          setTodaysCall(callResult)
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

  function handleStopSend() {
    abortRef.current?.abort()
  }

  async function handleSend(message, { restoreOnCancel } = {}) {
    const controller = new AbortController()
    abortRef.current = controller
    setSending(true)
    setError('')
    const optimisticId = `pending-${Date.now()}`
    const optimistic = {
      id: optimisticId,
      role: 'user',
      content: message,
      created_at: new Date().toISOString(),
    }
    setMessages((current) => [...current, optimistic])

    let chatMode
    if (weekFlowStep === 'review') {
      chatMode = 'week_plan_review'
    } else if (weekFlowStep === 'commit') {
      chatMode = 'week_plan_commit'
    }

    try {
      const result = await sendChatMessage(message, {
        activityId: focalActivityId,
        chatMode,
        signal: controller.signal,
      })
      setMessages(result.history || [])
      if (result.plan) {
        setPlan(result.plan)
        setStatus((current) => (current ? { ...current, has_active_plan: true } : current))
      }

      if (weekFlowStep === 'review' && !recoveryShift) {
        setWeekFlowStep('commit')
        const commitDraft = buildWeekCommitMessage(weekFlowContext, weekConstraints)
        setChatDraft(commitDraft)
        setDraftSeed(Date.now())
      } else if (weekFlowStep === 'review' && recoveryShift) {
        setWeekFlowStep(null)
        setRecoveryShift(false)
        setRecoveryPhase(null)
        if (profile?.id) clearWeekFlowState(profile.id)
      } else if (weekFlowStep === 'commit') {
        setWeekFlowStep(null)
        setRecoveryShift(false)
        setRecoveryPhase(null)
        if (profile?.id) clearWeekFlowState(profile.id)
      }
    } catch (err) {
      setMessages((current) => current.filter((item) => item.id !== optimisticId))
      if (err.name === 'AbortError') {
        restoreOnCancel?.(message)
        return
      }
      setError(err.message || 'Message failed to send.')
    } finally {
      abortRef.current = null
      setSending(false)
    }
  }

  const fitness = context?.coros?.fitness
  const composerHint =
    weekFlowStep === 'commit'
      ? 'Coach reviewed your week — edit if needed, then send to build the plan.'
      : weekFlowStep === 'review' && !recoveryShift
        ? 'Edit your schedule notes if needed, then send for a coach review.'
        : ''

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
              <CyclePhaseChip compact />
              <PlanActions
                plan={plan}
                publishing={publishing}
                onAddToSchedule={handleAddToSchedule}
              />
              <TodayAlertButton
                advice={advice}
                loading={adviceLoading && !advice}
                error={adviceError}
                onRefresh={() => loadAdvice(true)}
                refreshing={adviceLoading}
                health={context?.coros?.latest_health}
                fitness={fitness}
                callWarnings={todaysCall?.warnings}
                callLabel={todaysCall?.label}
                callDirective={todaysCall?.directive}
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
              onStop={handleStopSend}
              sending={sending}
              disabled={!consented}
              disabledReason="Enable AI coaching consent to chat."
              plan={plan}
              weekStart={weekStart}
              profileId={profile?.id}
              focalLabel={focalActivityName}
              onApplyWeek={handleApplyChatWeek}
              applyingWeek={publishing}
              onAddToSchedule={handleAddToSchedule}
              initialDraft={chatDraft}
              draftSeed={draftSeed}
              composerHint={composerHint}
            />
          </div>
        </div>
      )}
    </AppShell>
  )
}
