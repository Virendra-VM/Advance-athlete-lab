import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { CalendarRange, Flag, RefreshCw } from 'lucide-react'
import { generateSeason, getReplanTriggers, getSeason, replanSeason } from '../api/season'
import AppShell from '../components/layout/AppShell'
import EmptyState from '../components/ui/EmptyState'
import LoadingDots from '../components/ui/LoadingDots'
import PageHeader from '../components/ui/PageHeader'
import SectionCard from '../components/ui/SectionCard'

const PHASE_STYLES = {
  base: { bar: 'bg-indigo-700', chip: 'bg-indigo-500/15 text-indigo-700 dark:text-indigo-300' },
  build: { bar: 'bg-blue-500', chip: 'bg-blue-500/15 text-blue-700 dark:text-blue-300' },
  peak: { bar: 'bg-sky-500', chip: 'bg-sky-500/15 text-sky-700 dark:text-sky-300' },
  taper: { bar: 'bg-amber-500', chip: 'bg-amber-500/15 text-amber-700 dark:text-amber-300' },
  restore: { bar: 'bg-emerald-500', chip: 'bg-emerald-500/15 text-emerald-700 dark:text-emerald-300' },
  recovery_week: { bar: 'bg-slate-400', chip: 'bg-slate-500/15 text-slate-700 dark:text-slate-300' },
}

const PRIORITY_STYLES = {
  A: 'border-amber-400/40 bg-amber-500/10 text-amber-800 dark:text-amber-200',
  B: 'border-indigo-400/40 bg-indigo-500/10 text-indigo-800 dark:text-indigo-200',
  C: 'border-slate-400/30 bg-slate-500/10',
  D: 'border-teal-400/40 bg-teal-500/10 text-teal-800 dark:text-teal-200',
  E: 'border-[var(--aal-line)] bg-[var(--aal-accent-soft)]',
}

function formatDate(value) {
  if (!value) return '—'
  return new Date(`${value}T12:00:00`).toLocaleDateString(undefined, {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  })
}

function phaseLabel(type) {
  return (type || '').replace('_', ' ')
}

function daysBetween(start, end) {
  const a = new Date(`${start}T12:00:00`)
  const b = new Date(`${end}T12:00:00`)
  return Math.max(1, Math.round((b - a) / 86400000) + 1)
}

export default function SeasonPage() {
  const [season, setSeason] = useState(null)
  const [loading, setLoading] = useState(true)
  const [generating, setGenerating] = useState(false)
  const [replanning, setReplanning] = useState(false)
  const [replanTriggers, setReplanTriggers] = useState([])
  const [replanMessage, setReplanMessage] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false
    async function boot() {
      setLoading(true)
      setError('')
      try {
        const data = await getSeason()
        if (!cancelled) setSeason(data)
        if (!cancelled && data?.status === 'active') {
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

  async function handleReplan(force = false) {
    setReplanning(true)
    setError('')
    setReplanMessage('')
    try {
      const data = await replanSeason({ force })
      if (data.replanned && data.plan) {
        setSeason(data.plan)
        setReplanMessage(
          data.diff?.length
            ? data.message || 'Season replanned.'
            : data.message || 'Season updated — phases already matched the replan.',
        )
      } else {
        setReplanMessage(data.message || 'No replan needed.')
      }
      const triggers = await getReplanTriggers().catch(() => [])
      setReplanTriggers(triggers || [])
    } catch (err) {
      setError(err.message || 'Failed to replan season.')
    } finally {
      setReplanning(false)
    }
  }

  async function handleGenerate() {
    setGenerating(true)
    setError('')
    try {
      const data = await generateSeason()
      setSeason(data.plan)
    } catch (err) {
      setError(err.message || 'Failed to generate season plan.')
    } finally {
      setGenerating(false)
    }
  }

  const timeline = useMemo(() => {
    if (!season?.phases?.length || season.status === 'none') return null
    const start = season.start_date
    const end = season.end_date
    const totalDays = daysBetween(start, end)
    return season.phases.map((phase) => {
      const phaseDays = daysBetween(phase.start_date, phase.end_date)
      return {
        ...phase,
        widthPct: Math.max(4, (phaseDays / totalDays) * 100),
      }
    })
  }, [season])

  const hasPlan = season?.status === 'active' && season?.phases?.length > 0

  return (
    <AppShell title="Season">
      <PageHeader
        eyebrow="Training"
        title="Season plan"
        subtitle="Macro phases from today through your A-race — Base, Build, Peak, Taper, and Restore."
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <Link
              to="/profile#profile-training"
              className="rounded-xl border border-[var(--aal-line)] bg-[var(--aal-card)] px-3 py-2 text-sm font-medium transition hover:border-indigo-300 hover:text-indigo-600 dark:hover:text-indigo-300"
            >
              Edit A-race
            </Link>
            {hasPlan && replanTriggers.length > 0 ? (
              <button
                type="button"
                onClick={() => handleReplan(false)}
                disabled={replanning || loading}
                className="inline-flex items-center gap-2 rounded-xl border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-sm font-semibold text-amber-800 transition hover:bg-amber-500/20 disabled:opacity-60 dark:text-amber-200"
              >
                <RefreshCw className={`h-4 w-4 ${replanning ? 'animate-spin' : ''}`} />
                {replanning ? 'Replanning…' : 'Replan season'}
              </button>
            ) : null}
            <button
              type="button"
              onClick={handleGenerate}
              disabled={generating || loading}
              className="inline-flex items-center gap-2 rounded-xl bg-indigo-600 px-3 py-2 text-sm font-semibold text-white transition hover:bg-indigo-500 disabled:opacity-60"
            >
              <RefreshCw className={`h-4 w-4 ${generating ? 'animate-spin' : ''}`} />
              {generating ? 'Building…' : hasPlan ? 'Rebuild season' : 'Generate season'}
            </button>
          </div>
        }
      />

      {error ? <p className="mb-4 text-sm text-danger-muted">{error}</p> : null}
      {replanMessage ? (
        <p className="mb-4 text-sm text-indigo-700 dark:text-indigo-300">{replanMessage}</p>
      ) : null}
      {replanTriggers.length > 0 ? (
        <SectionCard className="mb-4">
          <p className="text-sm font-semibold text-[var(--aal-ink)]">Replan suggested</p>
          <ul className="mt-2 space-y-1 text-sm text-[var(--aal-muted)]">
            {replanTriggers.map((trigger) => (
              <li key={trigger.code}>• {trigger.message}</li>
            ))}
          </ul>
        </SectionCard>
      ) : null}

      {loading ? (
        <SectionCard>
          <LoadingDots label="Loading season…" />
        </SectionCard>
      ) : !season?.a_race ? (
        <EmptyState
          title="No A-race yet"
          description="Set your main goal event on Profile first, then generate your season plan."
          actionLabel="Go to Profile"
          actionTo="/profile#profile-training"
        />
      ) : (
        <div className="space-y-6">
          <div className="relative overflow-hidden rounded-2xl border border-[var(--aal-line)] px-4 py-4 sm:px-5 sm:py-5">
            <div
              className="pointer-events-none absolute inset-0"
              style={{
                background:
                  'radial-gradient(120% 80% at 0% 0%, rgba(55,48,163,0.12), transparent 55%), radial-gradient(90% 70% at 100% 20%, rgba(91,141,239,0.1), transparent 50%), linear-gradient(165deg, var(--aal-card), color-mix(in srgb, #312e81 5%, var(--aal-card)))',
              }}
            />
            <div className="relative flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
              <div className="flex items-start gap-3">
                <div className="rounded-xl bg-indigo-600/15 p-2 text-indigo-600 dark:text-indigo-300">
                  <Flag className="h-5 w-5" />
                </div>
                <div>
                  <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-indigo-500 dark:text-indigo-300">
                    A-race anchor
                  </p>
                  <h2 className="text-xl font-bold text-[var(--aal-ink)]">{season.a_race.name}</h2>
                  <p className="mt-1 text-sm text-[var(--aal-muted)]">
                    {formatDate(season.a_race.date)}
                    {season.a_race.target_metric ? ` · Target ${season.a_race.target_metric}` : ''}
                  </p>
                </div>
              </div>
              {season.current_phase ? (
                <div className="rounded-xl border border-indigo-500/20 bg-[var(--aal-card)]/80 px-4 py-3">
                  <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-indigo-500 dark:text-indigo-300">
                    Current phase
                  </p>
                  <p className="mt-1 text-lg font-bold capitalize text-[var(--aal-ink)]">
                    {phaseLabel(season.current_phase.phase_type)}
                    {season.week_in_phase ? (
                      <span className="ml-2 text-sm font-medium text-[var(--aal-muted)]">
                        week {season.week_in_phase}
                      </span>
                    ) : null}
                  </p>
                  <p className="mt-1 text-xs text-[var(--aal-muted)]">{season.current_phase.intent}</p>
                </div>
              ) : hasPlan ? null : (
                <p className="text-sm text-[var(--aal-muted)]">
                  Generate the season to see Base → Build → Peak → Taper blocks.
                </p>
              )}
            </div>
          </div>

          {season.warnings?.length ? (
            <SectionCard title="Planner warnings">
              <ul className="space-y-2 text-sm text-amber-800 dark:text-amber-200">
                {season.warnings.map((warning) => (
                  <li key={warning} className="rounded-lg bg-amber-500/10 px-3 py-2">
                    {warning}
                  </li>
                ))}
              </ul>
            </SectionCard>
          ) : null}

          {hasPlan && timeline ? (
            <>
              <SectionCard
                title="Phase timeline"
                subtitle={`${formatDate(season.start_date)} → ${formatDate(season.end_date)}`}
              >
                <div className="flex h-4 overflow-hidden rounded-full bg-slate-900/10 dark:bg-white/10">
                  {timeline.map((phase) => (
                    <div
                      key={`${phase.id}-${phase.start_date}`}
                      title={`${phaseLabel(phase.phase_type)} · ${formatDate(phase.start_date)} – ${formatDate(phase.end_date)}`}
                      className={`${PHASE_STYLES[phase.phase_type]?.bar || 'bg-indigo-400'} transition-[width]`}
                      style={{ width: `${phase.widthPct}%` }}
                    />
                  ))}
                </div>
                <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                  {season.phases.map((phase) => (
                    <div
                      key={phase.id}
                      className="rounded-xl border border-[var(--aal-line)] px-3 py-3"
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span
                          className={`rounded-full px-2 py-0.5 text-[10px] font-bold uppercase ${PHASE_STYLES[phase.phase_type]?.chip || ''}`}
                        >
                          {phaseLabel(phase.phase_type)}
                        </span>
                        <span className="text-xs text-[var(--aal-muted)]">
                          {formatDate(phase.start_date)} – {formatDate(phase.end_date)}
                        </span>
                      </div>
                      <p className="mt-2 text-sm text-[var(--aal-muted)]">{phase.intent}</p>
                      <p className="mt-2 text-xs text-[var(--aal-muted)]">
                        Long sessions up to {phase.long_session_allowed_min || '—'} min · volume bias{' '}
                        {phase.volume_bias ?? '—'}
                      </p>
                    </div>
                  ))}
                </div>
              </SectionCard>

              {season.upcoming_events?.length ? (
                <SectionCard title="Upcoming events" subtitle="Races and checkpoints in your season.">
                  <div className="space-y-2">
                    {season.upcoming_events.map((event) => (
                      <div
                        key={event.id}
                        className={`flex flex-wrap items-center justify-between gap-2 rounded-xl border px-3 py-2.5 ${PRIORITY_STYLES[event.priority] || PRIORITY_STYLES.E}`}
                      >
                        <div>
                          <span className="mr-2 text-[10px] font-bold uppercase">{event.priority}</span>
                          <span className="font-medium">{event.name}</span>
                        </div>
                        <span className="text-sm">{formatDate(event.date)}</span>
                      </div>
                    ))}
                  </div>
                </SectionCard>
              ) : null}

              {season.week_intent ? (
                <SectionCard
                  title="This week"
                  subtitle={`Phase focus for week of ${formatDate(season.week_intent.week_start)}`}
                >
                  <div className="grid gap-3 sm:grid-cols-3">
                    <div className="rounded-xl border border-[var(--aal-line)] px-3 py-3">
                      <p className="text-xs text-[var(--aal-muted)]">Intensity</p>
                      <p className="mt-1 font-semibold capitalize">{season.week_intent.intensity_bias}</p>
                    </div>
                    <div className="rounded-xl border border-[var(--aal-line)] px-3 py-3">
                      <p className="text-xs text-[var(--aal-muted)]">Volume bias</p>
                      <p className="mt-1 font-semibold tabular-nums">{season.week_intent.volume_bias}</p>
                    </div>
                    <div className="rounded-xl border border-[var(--aal-line)] px-3 py-3">
                      <p className="text-xs text-[var(--aal-muted)]">Long session cap</p>
                      <p className="mt-1 font-semibold tabular-nums">
                        {season.week_intent.long_session_allowed_min} min
                      </p>
                    </div>
                  </div>
                  {season.week_intent.notes?.length ? (
                    <ul className="mt-4 space-y-1.5 text-sm text-[var(--aal-muted)]">
                      {season.week_intent.notes.map((note) => (
                        <li key={note}>• {note}</li>
                      ))}
                    </ul>
                  ) : null}
                </SectionCard>
              ) : null}
            </>
          ) : (
            <SectionCard>
              <div className="flex items-start gap-3">
                <CalendarRange className="mt-0.5 h-5 w-5 text-indigo-500" />
                <div>
                  <p className="font-medium text-[var(--aal-ink)]">Ready to plan your season</p>
                  <p className="mt-1 text-sm text-[var(--aal-muted)]">
                    Generate macro phases working backward from {season.a_race.name}. Add B/C/D races
                    on Profile for tune-ups and tests.
                  </p>
                </div>
              </div>
            </SectionCard>
          )}
        </div>
      )}
    </AppShell>
  )
}
