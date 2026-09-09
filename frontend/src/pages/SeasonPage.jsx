import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import {
  AlertTriangle,
  CalendarRange,
  Flag,
  Gauge,
  Pencil,
  RefreshCw,
  ShieldCheck,
  Sparkles,
} from 'lucide-react'
import {
  adjustSeasonPhase,
  generateSeason,
  getReplanTriggers,
  getSeason,
  replanSeason,
} from '../api/season'
import { getCoachStatus, getWeekBrief } from '../api/coach'
import { WeekAlertButton } from '../components/coach/TodayAdvice'
import AppShell from '../components/layout/AppShell'
import PhaseDetailModal from '../components/season/PhaseDetailModal'
import RaceFeasibilityCard from '../components/season/RaceFeasibilityCard'
import ReplanResultCard from '../components/season/ReplanResultCard'
import SeasonActionDialog from '../components/season/SeasonActionDialog'
import SeasonBaselineCard from '../components/season/SeasonBaselineCard'
import SeasonTimeline from '../components/season/SeasonTimeline'
import SeasonWeekStrip from '../components/season/SeasonWeekStrip'
import LearnRow from '../components/training/LearnRow'
import EmptyState from '../components/ui/EmptyState'
import LoadingDots from '../components/ui/LoadingDots'
import PageHeader from '../components/ui/PageHeader'
import SectionCard from '../components/ui/SectionCard'
import {
  PRIORITY_GUIDES,
  SEASON_LEARN,
  TRIGGER_GUIDES,
  countdownLabel,
  daysUntil,
  formatMinutes,
  formatRange,
  formatSeasonDate,
  intensityLabel,
  isCurrentPhase,
  phaseAccent,
  phaseGuide,
  phaseLabel,
  volumeBiasLabel,
  weeksUntil,
} from '../utils/seasonGuides'
import { staggerContainer, staggerItem } from '../utils/statusColors'

function MetricTile({ label, value, hint }) {
  return (
    <div className="rounded-xl border border-[var(--aal-line)] bg-[var(--aal-card)] px-4 py-3">
      <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[var(--aal-muted)]">
        {label}
      </p>
      <p className="mt-1 text-lg font-bold text-[var(--aal-ink)]">{value}</p>
      {hint ? <p className="mt-0.5 text-xs text-[var(--aal-muted)]">{hint}</p> : null}
    </div>
  )
}

export default function SeasonPage() {
  const [season, setSeason] = useState(null)
  const [loading, setLoading] = useState(true)
  const [generating, setGenerating] = useState(false)
  const [replanning, setReplanning] = useState(false)
  const [replanTriggers, setReplanTriggers] = useState([])
  // Holds the whole replan response so the page can show what actually changed,
  // not just that something did.
  const [replanResult, setReplanResult] = useState(null)
  const [error, setError] = useState('')
  const [dialogMode, setDialogMode] = useState(null)
  const [phaseIndex, setPhaseIndex] = useState(null)
  const [adjusting, setAdjusting] = useState(false)
  const [adjustError, setAdjustError] = useState('')
  const [openLearn, setOpenLearn] = useState('retrograde')

  const [brief, setBrief] = useState(null)
  const [briefLoading, setBriefLoading] = useState(false)
  const [briefError, setBriefError] = useState('')
  const [consented, setConsented] = useState(false)

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

  // The brief explains an existing plan, so there is nothing to fetch until one exists.
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
      // The backend detects a newly added B or C race itself, but passing the
      // flag makes the trigger fire on the same visit the athlete added one
      // instead of waiting for the next signal sweep.
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
  const phases = useMemo(() => season?.phases || [], [season])
  const weekOutline = useMemo(() => season?.week_outline || [], [season])
  const aRace = season?.a_race || null
  const currentPhase = season?.current_phase || null
  const baseline = season?.baseline || null
  const feasibility = season?.a_race_feasibility || null
  const raceDays = aRace ? daysUntil(aRace.date) : null
  const raceWeeks = aRace ? weeksUntil(aRace.date) : null

  const currentIndex = useMemo(
    () => phases.findIndex((phase) => isCurrentPhase(phase)),
    [phases],
  )

  async function handleAdjustWeeks(phaseId, deltaWeeks) {
    setAdjusting(true)
    setAdjustError('')
    try {
      const plan = await adjustSeasonPhase(phaseId, deltaWeeks)
      setSeason(plan)
      if (consented) loadBrief(true)
    } catch (err) {
      setAdjustError(err.message || 'Could not move that week.')
    } finally {
      setAdjusting(false)
    }
  }

  function requestGenerate() {
    if (!hasPlan) {
      handleGenerate()
      return
    }
    setDialogMode('rebuild')
  }

  return (
    <AppShell title="Season">
      <PageHeader
        eyebrow="Training"
        title="Season plan"
        subtitle="Every phase is measured backward from your A-race — Base, Build, Peak, Taper, then Restore."
        actions={
          <div className="flex flex-wrap items-center gap-2">
            {hasPlan ? (
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
            ) : null}
            <button
              type="button"
              onClick={requestGenerate}
              disabled={generating || loading}
              className={
                hasPlan
                  ? 'inline-flex items-center gap-2 rounded-xl border border-[var(--aal-line)] bg-[var(--aal-card)] px-3 py-2 text-sm font-medium transition hover:border-indigo-300 hover:text-indigo-600 disabled:opacity-60 dark:hover:text-indigo-300'
                  : 'inline-flex items-center gap-2 rounded-xl bg-indigo-600 px-3 py-2 text-sm font-semibold text-white transition hover:bg-indigo-500 disabled:opacity-60'
              }
            >
              <RefreshCw className={`h-4 w-4 ${generating ? 'animate-spin' : ''}`} />
              {generating ? 'Building…' : hasPlan ? 'Rebuild season' : 'Generate season'}
            </button>
          </div>
        }
      />

      {error ? <p className="mb-4 text-sm text-danger-muted">{error}</p> : null}

      {loading ? (
        <SectionCard>
          <LoadingDots label="Loading season…" />
        </SectionCard>
      ) : !aRace ? (
        <EmptyState
          title="No A-race yet"
          description="Your season is built backward from one goal event. Set that race on Profile first, then generate the plan."
          actionLabel="Go to Profile"
          actionTo="/profile#profile-training"
        />
      ) : (
        <motion.div
          className="space-y-6"
          variants={staggerContainer}
          initial="hidden"
          animate="visible"
        >
          {replanResult ? (
            <motion.div variants={staggerItem}>
              <ReplanResultCard
                result={replanResult}
                onDismiss={() => setReplanResult(null)}
              />
            </motion.div>
          ) : null}

          {/* Hero: the anchor and where the athlete stands today. */}
          <motion.div
            variants={staggerItem}
            className="relative overflow-hidden rounded-2xl border border-[var(--aal-line)] px-4 py-5 sm:px-6"
          >
            <div
              className="pointer-events-none absolute inset-0"
              style={{
                background:
                  'radial-gradient(120% 80% at 0% 0%, rgba(55,48,163,0.14), transparent 55%), radial-gradient(90% 70% at 100% 20%, rgba(91,141,239,0.1), transparent 50%), linear-gradient(165deg, var(--aal-card), color-mix(in srgb, #312e81 6%, var(--aal-card)))',
              }}
            />
            <div className="relative flex flex-col gap-5 lg:flex-row lg:items-center lg:justify-between">
              <div className="flex items-start gap-3">
                <div className="shrink-0 rounded-xl bg-indigo-600/15 p-2.5 text-indigo-600 dark:text-indigo-300">
                  <Flag className="h-5 w-5" />
                </div>
                <div className="min-w-0">
                  <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-indigo-500 dark:text-indigo-300">
                    A-race anchor
                  </p>
                  <h2 className="mt-0.5 text-2xl font-bold leading-tight text-[var(--aal-ink)]">
                    {aRace.name}
                  </h2>
                  <p className="mt-1 text-sm text-[var(--aal-muted)]">
                    {formatSeasonDate(aRace.date)}
                    {aRace.target_metric ? ` · Target ${aRace.target_metric}` : ''}
                  </p>
                </div>
              </div>

              <div className="flex flex-wrap items-stretch gap-3">
                <div className="rounded-xl border border-indigo-500/25 bg-[var(--aal-card)]/85 px-4 py-3 text-center">
                  <p className="text-3xl font-bold tabular-nums leading-none text-indigo-600 dark:text-indigo-300">
                    {raceDays != null && raceDays >= 0 ? raceDays : '—'}
                  </p>
                  <p className="mt-1 text-[10px] font-semibold uppercase tracking-[0.14em] text-[var(--aal-muted)]">
                    days to go
                  </p>
                </div>

                {hasPlan && currentPhase ? (
                  <div className="min-w-[13rem] rounded-xl border border-indigo-500/25 bg-[var(--aal-card)]/85 px-4 py-3">
                    <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-indigo-500 dark:text-indigo-300">
                      You are here
                    </p>
                    <p className="mt-0.5 text-lg font-bold text-[var(--aal-ink)]">
                      {phaseLabel(currentPhase.phase_type)}
                      {season.week_in_phase ? (
                        <span className="ml-1.5 text-sm font-medium text-[var(--aal-muted)]">
                          week {season.week_in_phase} of {currentPhase.week_count}
                        </span>
                      ) : null}
                    </p>
                    <p className="mt-0.5 text-xs text-[var(--aal-muted)]">
                      {phaseGuide(currentPhase.phase_type).tagline} ·{' '}
                      {countdownLabel(aRace.date)}
                    </p>
                  </div>
                ) : null}
              </div>
            </div>
          </motion.div>

          {/* Replan suggestion sits above everything else because it is time-sensitive. */}
          {hasPlan && replanTriggers.length > 0 ? (
            <motion.div
              variants={staggerItem}
              className="rounded-2xl border border-amber-500/40 bg-amber-500/10 px-4 py-4 sm:px-5"
            >
              <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                <div className="flex items-start gap-3">
                  <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-amber-700 dark:text-amber-300" />
                  <div>
                    <p className="font-semibold text-amber-900 dark:text-amber-100">
                      Your training has drifted from this plan
                    </p>
                    <ul className="mt-1.5 space-y-1 text-sm text-amber-900/85 dark:text-amber-100/85">
                      {replanTriggers.map((trigger) => (
                        <li key={trigger.code}>
                          {TRIGGER_GUIDES[trigger.code]?.plain || trigger.message}
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => setDialogMode('replan')}
                  disabled={replanning}
                  className="inline-flex shrink-0 items-center justify-center gap-2 rounded-xl bg-indigo-600 px-3 py-2 text-sm font-semibold text-white transition hover:bg-indigo-500 disabled:opacity-60"
                >
                  <ShieldCheck className="h-4 w-4" />
                  {replanning ? 'Replanning…' : 'Review replan'}
                </button>
              </div>
            </motion.div>
          ) : null}

          {/* A read on the goal time — surfaced once a B-race has been raced. */}
          {hasPlan && feasibility ? (
            <motion.div variants={staggerItem}>
              <RaceFeasibilityCard feasibility={feasibility} aRace={aRace} />
            </motion.div>
          ) : null}

          {season.warnings?.length ? (
            <motion.div variants={staggerItem}>
              <SectionCard title="Planner warnings" subtitle="Worth a look before race week.">
                <ul className="space-y-2 text-sm text-amber-800 dark:text-amber-200">
                  {season.warnings.map((warning) => (
                    <li key={warning} className="rounded-lg bg-amber-500/10 px-3 py-2">
                      {warning}
                    </li>
                  ))}
                </ul>
              </SectionCard>
            </motion.div>
          ) : null}

          {hasPlan ? (
            <>
              <motion.div variants={staggerItem}>
                <SectionCard
                  title="Phase timeline"
                  subtitle={`${formatRange(season.start_date, season.end_date)} · tap a block for what it is for`}
                >
                  <SeasonTimeline
                    phases={phases}
                    startDate={season.start_date}
                    endDate={season.end_date}
                    events={season.upcoming_events}
                    onSelectPhase={setPhaseIndex}
                  />

                  {weekOutline.length ? (
                    <div className="mt-7 border-t border-[var(--aal-line)] pt-5">
                      <p className="mb-3 text-[10px] font-semibold uppercase tracking-[0.14em] text-[var(--aal-muted)]">
                        Week by week
                      </p>
                      <SeasonWeekStrip
                        weeks={weekOutline}
                        phases={phases}
                        onSelectPhase={setPhaseIndex}
                      />
                    </div>
                  ) : null}

                  <div className="mt-6 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                    {phases.map((phase, index) => {
                      const accent = phaseAccent(phase.phase_type)
                      const guide = phaseGuide(phase.phase_type)
                      const current = index === currentIndex
                      return (
                        <button
                          key={phase.id}
                          type="button"
                          onClick={() => setPhaseIndex(index)}
                          className={`rounded-xl border px-3.5 py-3 text-left transition hover:-translate-y-0.5 hover:shadow-sm ${
                            current
                              ? `${accent.ring} bg-[var(--aal-card)] shadow-sm`
                              : 'border-[var(--aal-line)] bg-[var(--aal-card)]/60 hover:border-indigo-300/50'
                          }`}
                        >
                          <div className="flex items-center justify-between gap-2">
                            <span
                              className={`rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide ${accent.chip}`}
                            >
                              {phaseLabel(phase.phase_type)}
                            </span>
                            {current ? (
                              <span className="text-[10px] font-bold uppercase tracking-wide text-indigo-600 dark:text-indigo-300">
                                Now
                              </span>
                            ) : (
                              <span className="text-xs tabular-nums text-[var(--aal-muted)]">
                                {phase.week_count} wk
                              </span>
                            )}
                          </div>
                          <p className="mt-2 text-sm font-semibold text-[var(--aal-ink)]">
                            {guide.tagline}
                          </p>
                          <p className="mt-1 text-xs text-[var(--aal-muted)]">
                            {formatRange(phase.start_date, phase.end_date)}
                          </p>
                        </button>
                      )
                    })}
                  </div>
                </SectionCard>
              </motion.div>

              {season.week_intent ? (
                <motion.div variants={staggerItem}>
                  <SectionCard
                    title="This week"
                    subtitle={`Week of ${formatSeasonDate(season.week_intent.week_start)} — how this block wants you to train`}
                    actions={
                      <Link
                        to="/coach"
                        className="inline-flex items-center gap-1.5 rounded-xl border border-[var(--aal-line)] px-3 py-1.5 text-xs font-medium transition hover:border-indigo-300 hover:text-indigo-600 dark:hover:text-indigo-300"
                      >
                        <Sparkles className="h-3.5 w-3.5" />
                        Get the sessions
                      </Link>
                    }
                  >
                    <div className="grid gap-3 sm:grid-cols-3">
                      <MetricTile
                        label="Intensity"
                        value={intensityLabel(season.week_intent.intensity_bias)}
                      />
                      <MetricTile
                        label="Volume"
                        value={volumeBiasLabel(season.week_intent.volume_bias)}
                        hint={`${season.week_intent.volume_bias}× bias`}
                      />
                      <MetricTile
                        label="Long day up to"
                        value={formatMinutes(season.week_intent.long_session_allowed_min)}
                        hint="Scaled to your longest recent session"
                      />
                    </div>
                    {season.week_intent.notes?.length ? (
                      <ul className="mt-4 space-y-2">
                        {season.week_intent.notes.map((note) => (
                          <li
                            key={note}
                            className="flex gap-2 text-sm leading-snug text-[var(--aal-muted)]"
                          >
                            <span
                              className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-indigo-500/60"
                              aria-hidden="true"
                            />
                            <span>{note}</span>
                          </li>
                        ))}
                      </ul>
                    ) : null}
                  </SectionCard>
                </motion.div>
              ) : null}

              {baseline ? (
                <motion.div variants={staggerItem}>
                  <SectionCard
                    title="Why these numbers"
                    subtitle="Your phase limits are scaled to the training you have actually done."
                  >
                    <SeasonBaselineCard baseline={baseline} />
                  </SectionCard>
                </motion.div>
              ) : null}

              {season.upcoming_events?.length ? (
                <motion.div variants={staggerItem}>
                  <SectionCard
                    title="Races ahead"
                    subtitle="How each priority is treated inside the plan."
                  >
                    <div className="space-y-2">
                      {season.upcoming_events.map((event) => {
                        const priority = PRIORITY_GUIDES[event.priority] || PRIORITY_GUIDES.E
                        return (
                          <div
                            key={event.id}
                            className={`flex flex-wrap items-center justify-between gap-x-3 gap-y-1 rounded-xl border px-3 py-2.5 ${priority.accent}`}
                          >
                            <div className="min-w-0">
                              <p className="font-medium">
                                <span className="mr-2 text-[10px] font-bold uppercase tracking-wide">
                                  {priority.label}
                                </span>
                                {event.name}
                              </p>
                              <p className="mt-0.5 text-xs opacity-80">{priority.meaning}</p>
                            </div>
                            <span className="text-sm tabular-nums">
                              {formatSeasonDate(event.date)}
                            </span>
                          </div>
                        )
                      })}
                    </div>
                  </SectionCard>
                </motion.div>
              ) : null}

              {/* The decision the athlete keeps getting wrong: Replan vs Rebuild. */}
              <motion.div variants={staggerItem}>
                <SectionCard
                  title="Manage this plan"
                  subtitle="Three different jobs — pick the smallest one that fixes your problem."
                >
                  <div className="grid gap-3 lg:grid-cols-3">
                    <Link
                      to="/profile#profile-training"
                      className="group rounded-xl border border-[var(--aal-line)] px-4 py-3.5 transition hover:border-indigo-300/60 hover:bg-indigo-50/40 dark:hover:bg-indigo-950/20"
                    >
                      <span className="inline-flex items-center gap-2 text-sm font-semibold text-[var(--aal-ink)]">
                        <Pencil className="h-4 w-4 text-indigo-500" />
                        Edit A-race
                      </span>
                      <p className="mt-1.5 text-xs leading-relaxed text-[var(--aal-muted)]">
                        The date or event changed. Change it here first, then rebuild so the phases
                        land correctly.
                      </p>
                    </Link>

                    <button
                      type="button"
                      onClick={() => setDialogMode('replan')}
                      disabled={replanning}
                      className="rounded-xl border border-[var(--aal-line)] px-4 py-3.5 text-left transition hover:border-indigo-300/60 hover:bg-indigo-50/40 disabled:opacity-60 dark:hover:bg-indigo-950/20"
                    >
                      <span className="inline-flex items-center gap-2 text-sm font-semibold text-[var(--aal-ink)]">
                        <ShieldCheck className="h-4 w-4 text-indigo-500" />
                        Replan remaining weeks
                      </span>
                      <p className="mt-1.5 text-xs leading-relaxed text-[var(--aal-muted)]">
                        Missed sessions, an injury, a new B or C race, or load climbing too fast.
                        Finished weeks stay.
                        {replanTriggers.length > 0 ? (
                          <span className="mt-1 block font-semibold text-amber-700 dark:text-amber-300">
                            {replanTriggers.length} reason
                            {replanTriggers.length === 1 ? '' : 's'} to replan right now
                          </span>
                        ) : null}
                      </p>
                    </button>

                    <button
                      type="button"
                      onClick={() => setDialogMode('rebuild')}
                      disabled={generating}
                      className="rounded-xl border border-[var(--aal-line)] px-4 py-3.5 text-left transition hover:border-amber-400/60 hover:bg-amber-50/40 disabled:opacity-60 dark:hover:bg-amber-950/20"
                    >
                      <span className="inline-flex items-center gap-2 text-sm font-semibold text-[var(--aal-ink)]">
                        <RefreshCw className="h-4 w-4 text-amber-600 dark:text-amber-400" />
                        Rebuild from scratch
                      </span>
                      <p className="mt-1.5 text-xs leading-relaxed text-[var(--aal-muted)]">
                        Starts the whole timeline again from today. Use it for a new season or after
                        changing your A-race — it does not keep finished weeks.
                      </p>
                    </button>
                  </div>
                </SectionCard>
              </motion.div>
            </>
          ) : (
            <motion.div variants={staggerItem}>
              <SectionCard>
                <div className="flex items-start gap-3">
                  <CalendarRange className="mt-0.5 h-5 w-5 shrink-0 text-indigo-500" />
                  <div>
                    <p className="font-semibold text-[var(--aal-ink)]">Ready to plan your season</p>
                    <p className="mt-1 text-sm leading-relaxed text-[var(--aal-muted)]">
                      We will count backward from {aRace.name} and split the{' '}
                      {raceWeeks != null ? `${raceWeeks} weeks` : 'weeks'} left into Base, Build,
                      Peak, and Taper, with recovery weeks built in. Add B, C, and D events on
                      Profile first if you have them — they change how the weeks are shared out.
                    </p>
                    <button
                      type="button"
                      onClick={handleGenerate}
                      disabled={generating}
                      className="mt-4 inline-flex items-center gap-2 rounded-xl bg-indigo-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-indigo-500 disabled:opacity-60"
                    >
                      <Gauge className={`h-4 w-4 ${generating ? 'animate-spin' : ''}`} />
                      {generating ? 'Building…' : 'Generate season'}
                    </button>
                  </div>
                </div>
              </SectionCard>
            </motion.div>
          )}

          <motion.section
            variants={staggerItem}
            className="rounded-2xl border border-[var(--aal-line)] bg-[var(--aal-card)] px-5 sm:px-6"
          >
            <div className="pt-5">
              <h2 className="text-lg font-semibold text-[var(--aal-ink)]">
                How this season was planned
              </h2>
              <p className="mt-1 text-sm text-[var(--aal-muted)]">
                Short answers first. The phase dates come from a periodization engine, not a
                template you have to trust blindly.
              </p>
            </div>
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
          </motion.section>
        </motion.div>
      )}

      <PhaseDetailModal
        phases={phases}
        index={phaseIndex}
        events={season?.upcoming_events || []}
        weekIntent={season?.week_intent}
        adjusting={adjusting}
        adjustError={adjustError}
        onAdjustWeeks={handleAdjustWeeks}
        onClose={() => {
          setPhaseIndex(null)
          setAdjustError('')
        }}
        onNavigate={(next) => {
          setPhaseIndex(next)
          setAdjustError('')
        }}
      />

      <SeasonActionDialog
        mode={dialogMode}
        triggers={replanTriggers}
        aRace={aRace}
        busy={dialogMode === 'rebuild' ? generating : replanning}
        onCancel={() => setDialogMode(null)}
        onConfirm={() => (dialogMode === 'rebuild' ? handleGenerate() : handleReplan(true))}
        onUseReplan={() => setDialogMode('replan')}
      />
    </AppShell>
  )
}
