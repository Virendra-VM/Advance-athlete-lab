import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { AlertTriangle, CheckCircle2, RefreshCw, Sparkles } from 'lucide-react'
import {
  adjustSeasonPhase,
  deleteSeasonPhase,
  replaceSeasonPhase,
  shiftRecoveryPhase,
  generateSeason,
  getReplanTriggers,
  getSeason,
  getSeasonAudit,
  getSeasonPreview,
  replanSeason,
} from '../api/season'
import { useAuth } from '../context/AuthContext'
import { getCoachStatus, getWeekBrief, getWeekPlan } from '../api/coach'
import { WeekAlertButton } from '../components/coach/TodayAdvice'
import AppShell from '../components/layout/AppShell'
import DismissibleBanner from '../components/season/DismissibleBanner'
import PhaseDetailModal from '../components/season/PhaseDetailModal'
import RaceFeasibilityCard from '../components/season/RaceFeasibilityCard'
import ReplanResultModal from '../components/season/ReplanResultModal'
import SeasonActionDialog from '../components/season/SeasonActionDialog'
import SeasonAuditModal from '../components/season/SeasonAuditModal'
import SeasonFeedbackModal from '../components/season/SeasonFeedbackModal'
import SeasonOnboarding from '../components/season/SeasonOnboarding'
import SeasonPlanMenu from '../components/season/SeasonPlanMenu'
import SeasonPlanPreviewModal from '../components/season/SeasonPlanPreviewModal'
import SeasonStatusHero from '../components/season/SeasonStatusHero'
import SeasonSupportingPanel from '../components/season/SeasonSupportingPanel'
import SeasonTimeline from '../components/season/SeasonTimeline'
import SeasonWeekFocus from '../components/season/SeasonWeekFocus'
import SeasonWeekStrip from '../components/season/SeasonWeekStrip'
import LearnRow from '../components/training/LearnRow'
import EmptyState from '../components/ui/EmptyState'
import LoadingDots from '../components/ui/LoadingDots'
import SectionCard from '../components/ui/SectionCard'
import {
  SEASON_LEARN,
  TRIGGER_GUIDES,
  daysUntil,
  formatRange,
  phaseLabel,
  weeksUntil,
} from '../utils/seasonGuides'
import { staggerContainer, staggerItem } from '../utils/statusColors'

export default function SeasonPage() {
  const navigate = useNavigate()
  const { updateProfile } = useAuth()
  const [season, setSeason] = useState(null)
  const [loading, setLoading] = useState(true)
  const [generating, setGenerating] = useState(false)
  const [replanning, setReplanning] = useState(false)
  const [replanTriggers, setReplanTriggers] = useState([])
  const [replanResult, setReplanResult] = useState(null)
  const [error, setError] = useState('')
  const [dialogMode, setDialogMode] = useState(null)
  const [phaseIndex, setPhaseIndex] = useState(null)
  const [adjusting, setAdjusting] = useState(false)
  const [adjustError, setAdjustError] = useState('')
  const [openLearn, setOpenLearn] = useState(null)
  const [learnOpen, setLearnOpen] = useState(false)
  const [previewOpen, setPreviewOpen] = useState(false)
  const [previewMode, setPreviewMode] = useState('generate')
  const [preview, setPreview] = useState(null)
  const [previewLoading, setPreviewLoading] = useState(false)
  const [previewError, setPreviewError] = useState('')
  const [planningNotes, setPlanningNotes] = useState('')

  const [brief, setBrief] = useState(null)
  const [briefLoading, setBriefLoading] = useState(false)
  const [briefError, setBriefError] = useState('')
  const [consented, setConsented] = useState(false)
  const [currentWeekPlan, setCurrentWeekPlan] = useState(null)
  const [weekPlanLoading, setWeekPlanLoading] = useState(false)
  const [auditOpen, setAuditOpen] = useState(false)
  const [audit, setAudit] = useState(null)
  const [auditLoading, setAuditLoading] = useState(false)
  const [auditError, setAuditError] = useState('')
  const [feedback, setFeedback] = useState(null)

  const loadBrief = useCallback(async (force = false) => {
    setBriefLoading(true)
    setBriefError('')
    try {
      setBrief(await getWeekBrief({ refresh: Boolean(force), topic: 'season' }))
    } catch (err) {
      setBriefError(err.message || 'Could not load your season brief.')
    } finally {
      setBriefLoading(false)
    }
  }, [])

  useEffect(() => {
    let cancelled = false
    async function boot() {
      setLoading(true)
      setError('')
      try {
        const data = await getSeason()
        if (cancelled) return
        setSeason(data)
        if (data?.status === 'active') {
          const triggers = await getReplanTriggers().catch(() => [])
          if (!cancelled) setReplanTriggers(triggers || [])
        }
      } catch (err) {
        if (!cancelled) setError(err.message || 'Failed to load season plan.')
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    boot()
    return () => {
      cancelled = true
    }
  }, [])

  const planActive = season?.status === 'active'

  useEffect(() => {
    if (!planActive) return undefined
    let cancelled = false
    async function bootBrief() {
      const statusResult = await getCoachStatus().catch(() => null)
      if (cancelled) return
      const aiOn = Boolean(statusResult?.ai_consent)
      setConsented(aiOn)
      if (aiOn) loadBrief(false)
      else setBriefError('Turn on AI coaching in settings to get a season brief.')
    }
    bootBrief()
    return () => {
      cancelled = true
    }
  }, [planActive, loadBrief])

  async function handleReplan(force = false) {
    setReplanning(true)
    setError('')
    setReplanResult(null)
    try {
      const data = await replanSeason({
        force,
        new_bc_race: replanTriggers.some((trigger) => trigger.code === 'new_bc_race'),
      })
      if (data.replanned && data.plan) setSeason(data.plan)
      setReplanResult({
        ...data,
        message:
          data.message ||
          (data.replanned
            ? 'Remaining weeks updated. Finished weeks were left untouched.'
            : 'Nothing needed changing — your plan already fits.'),
      })
      const triggers = data.triggers ?? (await getReplanTriggers().catch(() => []))
      setReplanTriggers(triggers || [])
      setDialogMode(null)
      if (consented) loadBrief(true)
    } catch (err) {
      setError(err.message || 'Failed to replan season.')
    } finally {
      setReplanning(false)
    }
  }

  async function handleGenerate() {
    setGenerating(true)
    setError('')
    setReplanResult(null)
    try {
      const data = await generateSeason()
      setSeason(data.plan)
      const triggers = await getReplanTriggers().catch(() => [])
      setReplanTriggers(triggers || [])
      setDialogMode(null)
      setReplanResult({
        replanned: true,
        message: 'New timeline drawn from today through race day.',
        summary: [],
        diff: [],
      })
      if (consented) loadBrief(true)
    } catch (err) {
      setError(err.message || 'Failed to generate season plan.')
      setDialogMode(null)
    } finally {
      setGenerating(false)
    }
  }

  const hasPlan = season?.status === 'active' && season?.phases?.length > 0
  const weekAlreadyPlanned = Boolean(currentWeekPlan?.plan?.workouts?.length)

  useEffect(() => {
    if (!hasPlan) {
      setCurrentWeekPlan(null)
      return undefined
    }
    let cancelled = false
    async function loadCurrentWeekPlan() {
      setWeekPlanLoading(true)
      try {
        const weekStart = season?.week_intent?.week_start || null
        const plan = await getWeekPlan(weekStart).catch(() => null)
        if (!cancelled) setCurrentWeekPlan(plan)
      } finally {
        if (!cancelled) setWeekPlanLoading(false)
      }
    }
    loadCurrentWeekPlan()
    return () => {
      cancelled = true
    }
  }, [hasPlan, season?.week_intent?.week_start])

  const phases = useMemo(() => season?.phases || [], [season])
  const weekOutline = useMemo(() => season?.week_outline || [], [season])
  const aRace = season?.a_race || null
  const currentPhase = season?.current_phase || null
  const baseline = season?.baseline || null
  const feasibility = season?.a_race_feasibility || null
  const raceDays = aRace ? daysUntil(aRace.date) : null
  const raceWeeks = aRace ? weeksUntil(aRace.date) : null

  const hasAlerts =
    (hasPlan && replanTriggers.length > 0) || (season?.warnings?.length ?? 0) > 0

  function showPhaseFeedback(variant, title, message) {
    setPhaseIndex(null)
    setAdjustError('')
    setFeedback({ variant, title, message })
  }

  async function handleAdjustWeeks(phaseId, deltaWeeks) {
    setAdjusting(true)
    setAdjustError('')
    try {
      const plan = await adjustSeasonPhase(phaseId, deltaWeeks)
      setSeason(plan)
      showPhaseFeedback(
        'success',
        'Block updated',
        deltaWeeks > 0 ? 'One week added to this block.' : 'One week removed from this block.',
      )
      if (consented) loadBrief(true)
    } catch (err) {
      setAdjustError(err.message || 'Could not move that week.')
    } finally {
      setAdjusting(false)
    }
  }

  async function handleShiftRecovery(phaseId, targetWeekStart) {
    setAdjusting(true)
    setAdjustError('')
    try {
      const plan = await shiftRecoveryPhase(phaseId, targetWeekStart)
      setSeason(plan)
      showPhaseFeedback('success', 'Recovery week moved', `Block now starts ${targetWeekStart}.`)
      if (consented) loadBrief(true)
    } catch (err) {
      setAdjustError(err.message || 'Could not place recovery on that week.')
    } finally {
      setAdjusting(false)
    }
  }

  async function handleDeletePhase(phaseId, mergeInto = 'next') {
    setAdjusting(true)
    setAdjustError('')
    try {
      const plan = await deleteSeasonPhase(phaseId, mergeInto)
      setSeason(plan)
      showPhaseFeedback(
        'success',
        'Week removed',
        `Merged into the ${mergeInto === 'prev' ? 'previous' : 'next'} block.`,
      )
      if (consented) loadBrief(true)
    } catch (err) {
      setAdjustError(err.message || 'Could not remove that week.')
    } finally {
      setAdjusting(false)
    }
  }

  async function handleReplacePhase(phaseId, newPhaseType) {
    setAdjusting(true)
    setAdjustError('')
    try {
      const plan = await replaceSeasonPhase(phaseId, newPhaseType)
      setSeason(plan)
      showPhaseFeedback(
        'success',
        'Block replaced',
        `This week is now a ${phaseLabel(newPhaseType)} block.`,
      )
      if (consented) loadBrief(true)
    } catch (err) {
      setAdjustError(err.message || 'Could not replace that block.')
    } finally {
      setAdjusting(false)
    }
  }

  async function openPreview(mode = 'generate') {
    setPreviewMode(mode)
    setPreviewOpen(true)
    setPreviewLoading(true)
    setPreviewError('')
    setPreview(null)
    try {
      const data = await getSeasonPreview()
      setPreview(data)
      setPlanningNotes(data?.profile?.planning_notes || '')
    } catch (err) {
      setPreviewError(err.message || 'Could not load season preview.')
    } finally {
      setPreviewLoading(false)
    }
  }

  async function confirmPreview() {
    setPreviewError('')
    try {
      const savedNotes = preview?.profile?.planning_notes || ''
      const trimmed = (planningNotes || '').trim()
      if (trimmed !== (savedNotes || '').trim()) {
        await updateProfile({ planning_notes: trimmed || null })
      }
      setPreviewOpen(false)
      await handleGenerate()
    } catch (err) {
      setPreviewError(err.message || 'Could not save or plan your season.')
    }
  }

  function requestGenerate() {
    if (!hasPlan) {
      openPreview('generate')
      return
    }
    setDialogMode('rebuild')
  }

  function goPlanWeek({ recoveryPhase = null } = {}) {
    if (!consented) {
      navigate('/settings#privacy')
      return
    }
    navigate('/coach', {
      state: {
        weekPlanFlow: true,
        recoveryShift: Boolean(recoveryPhase),
        recoveryPhase: recoveryPhase || null,
      },
    })
  }

  async function openAudit() {
    setAuditOpen(true)
    setAuditLoading(true)
    setAuditError('')
    setAudit(null)
    try {
      setAudit(await getSeasonAudit())
    } catch (err) {
      setAuditError(err.message || 'Could not run season audit.')
    } finally {
      setAuditLoading(false)
    }
  }

  function handleAuditAction(action) {
    setAuditOpen(false)
    if (action === 'replan') {
      setDialogMode('replan')
      return
    }
    if (action === 'rebuild') {
      setDialogMode('rebuild')
      return
    }
    if (action === 'coach') {
      goPlanWeek()
      return
    }
    if (action === 'profile') {
      navigate('/profile')
    }
  }

  return (
    <AppShell title="Season" fill>
      <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
        {/* Sticky toolbar — coach brief + plan options only */}
        <header className="relative z-20 flex shrink-0 flex-wrap items-center justify-between gap-2 border-b border-[var(--aal-line)] bg-[var(--aal-card)]/90 px-3 py-2 backdrop-blur-sm sm:px-5">
          <div className="flex min-w-0 flex-1 flex-wrap items-center gap-2 pl-10 lg:pl-0">
            <div className="min-w-0">
              <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-indigo-500 dark:text-indigo-300">
                Training
              </p>
              <p className="truncate text-sm font-semibold text-[var(--aal-ink)]">Season plan</p>
              <p className="truncate text-[11px] text-[var(--aal-muted)]">
                {hasPlan && currentPhase
                  ? `${phaseLabel(currentPhase.phase_type)} · ${raceWeeks ?? '—'} weeks to race`
                  : 'Roadmap from your goal race'}
              </p>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {hasPlan ? (
              <>
                {weekPlanLoading ? null : weekAlreadyPlanned ? (
                  <span className="inline-flex shrink-0 items-center gap-1.5 rounded-xl border border-sage/35 bg-sage/10 px-3 py-1.5 text-xs font-semibold text-sage">
                    <CheckCircle2 className="h-3.5 w-3.5" />
                    Week already planned
                  </span>
                ) : (
                  <button
                    type="button"
                    onClick={() => goPlanWeek()}
                    disabled={loading || weekPlanLoading}
                    className="inline-flex shrink-0 items-center gap-1.5 rounded-xl border border-sage/40 bg-sage/10 px-3 py-1.5 text-xs font-semibold text-sage transition hover:bg-sage/20 disabled:opacity-60 sm:text-sm sm:px-3 sm:py-2"
                  >
                    <Sparkles className="h-3.5 w-3.5 sm:h-4 sm:w-4" />
                    Plan this week
                  </button>
                )}
                <WeekAlertButton
                  topic="season"
                  advice={brief}
                  loading={briefLoading && !brief}
                  error={briefError}
                  onRefresh={() => (consented ? loadBrief(true) : null)}
                  refreshing={briefLoading}
                  loadChips={[
                    {
                      label: 'Phase',
                      value: currentPhase ? phaseLabel(currentPhase.phase_type) : null,
                    },
                    {
                      label: 'To race',
                      value: raceWeeks != null ? `${raceWeeks} wk` : null,
                    },
                    {
                      label: 'Volume',
                      value: season?.week_intent?.volume_bias ?? null,
                    },
                  ]}
                />
                <SeasonPlanMenu
                  disabled={loading || generating || replanning}
                  replanTriggerCount={replanTriggers.length}
                  onReplan={() => setDialogMode('replan')}
                  onRebuildFromScratch={() => setDialogMode('rebuild')}
                  onRebuildSeason={() => openPreview('rebuild')}
                />
              </>
            ) : aRace ? (
              <button
                type="button"
                onClick={requestGenerate}
                disabled={generating || loading || previewLoading}
                className="inline-flex items-center gap-2 rounded-xl bg-indigo-600 px-3 py-2 text-sm font-semibold text-white transition hover:bg-indigo-500 disabled:opacity-60"
              >
                <RefreshCw className={`h-4 w-4 ${generating || previewLoading ? 'animate-spin' : ''}`} />
                {generating || previewLoading ? 'Loading…' : 'Generate roadmap'}
              </button>
            ) : null}
          </div>
        </header>

        {error ? (
          <p className="shrink-0 border-b border-red-200/60 bg-red-50/80 px-4 py-2 text-sm text-danger-muted dark:bg-red-950/30">
            {error}
          </p>
        ) : null}

        {loading ? (
          <div className="flex min-h-0 flex-1 items-center justify-center">
            <LoadingDots label="Loading season…" />
          </div>
        ) : !aRace ? (
          <div className="min-h-0 flex-1 overflow-y-auto p-4 sm:p-6">
            <EmptyState
              title="Set your goal race first"
              description="Your season is built backward from one A-race. Add it on Profile, then come back to generate your roadmap."
              actionLabel="Go to Profile"
              actionTo="/profile#profile-training"
            />
          </div>
        ) : (
          <div className="min-h-0 flex-1 overflow-y-auto px-4 py-5 sm:px-6 lg:px-8">
            <motion.div
              className="space-y-5"
              variants={staggerContainer}
              initial="hidden"
              animate="visible"
            >
              {/* 1 · Status — goal, phase, countdown, primary CTA */}
              <motion.div variants={staggerItem}>
                <SeasonStatusHero
                  aRace={aRace}
                  raceDays={raceDays}
                  currentPhase={currentPhase}
                  weekInPhase={season?.week_in_phase}
                  seasonStart={season?.start_date}
                  seasonEnd={season?.end_date}
                  hasPlan={hasPlan}
                />
              </motion.div>

              {/* 2 · Alerts — only when something needs attention */}
              {hasAlerts ? (
                <motion.div variants={staggerItem} className="space-y-2">
                  {hasPlan && replanTriggers.length > 0 ? (
                    <DismissibleBanner
                      id={`replan-${replanTriggers.map((t) => t.code).join('-')}`}
                      icon={AlertTriangle}
                      title={`Plan may be out of date — ${replanTriggers.length} signal${replanTriggers.length === 1 ? '' : 's'}`}
                      action={
                        <button
                          type="button"
                          onClick={() => setDialogMode('replan')}
                          disabled={replanning}
                          className="rounded-lg bg-indigo-600 px-2.5 py-1 text-xs font-semibold text-white transition hover:bg-indigo-500 disabled:opacity-60"
                        >
                          {replanning ? '…' : 'Review replan'}
                        </button>
                      }
                    >
                      <ul className="space-y-1">
                        {replanTriggers.map((trigger) => (
                          <li key={trigger.code}>
                            {TRIGGER_GUIDES[trigger.code]?.plain || trigger.message}
                          </li>
                        ))}
                      </ul>
                    </DismissibleBanner>
                  ) : null}
                  {season.warnings?.length ? (
                    <DismissibleBanner
                      id={`warnings-${season.warnings.join('|')}`}
                      icon={AlertTriangle}
                      title={`${season.warnings.length} planner note${season.warnings.length === 1 ? '' : 's'}`}
                    >
                      <ul className="space-y-1">
                        {season.warnings.map((warning) => (
                          <li key={warning}>{warning}</li>
                        ))}
                      </ul>
                    </DismissibleBanner>
                  ) : null}
                </motion.div>
              ) : null}

              {hasPlan && feasibility ? (
                <motion.div variants={staggerItem}>
                  <RaceFeasibilityCard feasibility={feasibility} aRace={aRace} />
                </motion.div>
              ) : null}

              {hasPlan ? (
                <>
                  {/* 3 · Roadmap — full-width timeline */}
                  <motion.div variants={staggerItem}>
                    <SectionCard
                      title="Season roadmap"
                      subtitle={`${formatRange(season.start_date, season.end_date)} · Today’s line shows where you are · Tap any block for details`}
                      actions={
                        <button
                          type="button"
                          onClick={openAudit}
                          disabled={auditLoading}
                          className="inline-flex shrink-0 items-center gap-1.5 rounded-xl border border-indigo-500/30 bg-indigo-500/10 px-3 py-1.5 text-xs font-semibold text-indigo-700 transition hover:bg-indigo-500/15 disabled:opacity-60 dark:text-indigo-200"
                        >
                          <Sparkles className="h-3.5 w-3.5" />
                          Periodization audit
                        </button>
                      }
                    >
                      <SeasonTimeline
                        phases={phases}
                        startDate={season.start_date}
                        endDate={season.end_date}
                        events={season.upcoming_events}
                        onSelectPhase={setPhaseIndex}
                        onShiftPhase={handleShiftRecovery}
                        shifting={adjusting}
                      />
                      {weekOutline.length ? (
                        <div className="mt-5 border-t border-[var(--aal-line)] pt-4">
                          <p className="mb-2 text-[10px] font-semibold uppercase tracking-[0.14em] text-[var(--aal-muted)]">
                            Week by week
                          </p>
                          <SeasonWeekStrip
                            weeks={weekOutline}
                            phases={phases}
                            onSelectPhase={setPhaseIndex}
                          />
                        </div>
                      ) : null}
                    </SectionCard>
                  </motion.div>

                  {/* 4 · This week — actionable focus */}
                  <motion.div variants={staggerItem}>
                    <SeasonWeekFocus
                      weekIntent={season.week_intent}
                      weekAlreadyPlanned={weekAlreadyPlanned}
                      onPlanWeek={weekAlreadyPlanned ? null : () => goPlanWeek()}
                    />
                  </motion.div>

                  {/* 5 · Supporting context */}
                  <motion.div variants={staggerItem}>
                    <SeasonSupportingPanel
                      events={season.upcoming_events}
                      baseline={baseline}
                    />
                  </motion.div>
                </>
              ) : (
                <motion.div variants={staggerItem}>
                  <SeasonOnboarding
                    aRace={aRace}
                    raceWeeks={raceWeeks}
                    generating={generating || previewLoading}
                    onGenerate={requestGenerate}
                  />
                </motion.div>
              )}

              {/* 6 · Learn — optional depth */}
              <motion.section variants={staggerItem}>
                <button
                  type="button"
                  onClick={() => setLearnOpen((current) => !current)}
                  className="flex w-full items-center justify-between gap-3 rounded-xl border border-dashed border-[var(--aal-line)] bg-[var(--aal-card)]/60 px-4 py-3 text-left transition hover:border-indigo-300/50 hover:bg-[var(--aal-card)]"
                >
                  <div>
                    <p className="text-sm font-semibold text-[var(--aal-ink)]">
                      How season planning works
                    </p>
                    <p className="text-xs text-[var(--aal-muted)]">
                      Phases, replan vs rebuild, and where the dates come from
                    </p>
                  </div>
                  <span className="shrink-0 text-xs font-medium text-indigo-500">
                    {learnOpen ? 'Hide' : 'Learn more'}
                  </span>
                </button>
                {learnOpen ? (
                  <div className="mt-2 rounded-xl border border-[var(--aal-line)] bg-[var(--aal-card)] px-4 sm:px-5">
                    {SEASON_LEARN.map((topic) => (
                      <LearnRow
                        key={topic.id}
                        topic={topic}
                        open={openLearn === topic.id}
                        onToggle={() =>
                          setOpenLearn((current) => (current === topic.id ? null : topic.id))
                        }
                      />
                    ))}
                  </div>
                ) : null}
              </motion.section>
            </motion.div>
          </div>
        )}
      </div>

      <PhaseDetailModal
        phases={phases}
        index={phaseIndex}
        events={season?.upcoming_events || []}
        weekIntent={season?.week_intent}
        adjusting={adjusting}
        adjustError={adjustError}
        onAdjustWeeks={handleAdjustWeeks}
        onShiftRecovery={handleShiftRecovery}
        onDeletePhase={handleDeletePhase}
        onReplacePhase={handleReplacePhase}
        onClose={() => {
          setPhaseIndex(null)
          setAdjustError('')
        }}
        onNavigate={(next) => {
          setPhaseIndex(next)
          setAdjustError('')
        }}
        onPlanRecoveryWeek={(phase) => {
          setPhaseIndex(null)
          goPlanWeek({ recoveryPhase: phase })
        }}
      />

      <SeasonActionDialog
        mode={dialogMode}
        triggers={replanTriggers}
        aRace={aRace}
        busy={dialogMode === 'rebuild' ? generating : replanning}
        onCancel={() => setDialogMode(null)}
        onConfirm={() => {
          if (dialogMode === 'rebuild') {
            setDialogMode(null)
            openPreview('rebuild')
            return
          }
          handleReplan(true)
        }}
        onUseReplan={() => setDialogMode('replan')}
      />

      <SeasonPlanPreviewModal
        open={previewOpen}
        preview={preview}
        mode={previewMode}
        planningNotes={planningNotes}
        onPlanningNotesChange={setPlanningNotes}
        busy={generating}
        loading={previewLoading}
        error={previewError}
        onCancel={() => {
          if (generating) return
          setPreviewOpen(false)
          setPreviewError('')
        }}
        onConfirm={confirmPreview}
      />

      <SeasonAuditModal
        open={auditOpen}
        audit={audit}
        loading={auditLoading}
        error={auditError}
        onClose={() => setAuditOpen(false)}
        onAction={handleAuditAction}
      />

      <ReplanResultModal
        open={Boolean(replanResult)}
        result={replanResult}
        onClose={() => setReplanResult(null)}
      />

      <SeasonFeedbackModal
        open={Boolean(feedback)}
        variant={feedback?.variant || 'success'}
        title={feedback?.title || ''}
        message={feedback?.message || ''}
        onClose={() => setFeedback(null)}
      />
    </AppShell>
  )
}
