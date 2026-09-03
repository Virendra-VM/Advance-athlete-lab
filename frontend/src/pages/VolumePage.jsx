import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { getAthleteStats } from '../api/athlete'
import { getCoachStatus, getWeekBrief } from '../api/coach'
import { getCoachContext } from '../api/coros'
import { useAuth } from '../context/AuthContext'
import BarActiveGlow from '../components/charts/BarActiveEffects'
import { WeekAlertButton } from '../components/coach/TodayAdvice'
import AppShell from '../components/layout/AppShell'
import ACWRGauge from '../components/ACWRGauge'
import LearnRow from '../components/training/LearnRow'
import LoadEquation from '../components/training/LoadEquation'
import AcwrZoneStrip from '../components/training/AcwrZoneStrip'
import EmptyState from '../components/ui/EmptyState'
import LoadingDots from '../components/ui/LoadingDots'
import SectionCard from '../components/ui/SectionCard'
import { ACWR_ZONES, hasLoadHistory, interpretLoad, isSparseBaseline, LOAD_LEARN } from '../utils/loadGuides'
import { staggerContainer, staggerItem } from '../utils/statusColors'

function VolumeTooltip({ active, payload }) {
  if (!active || !payload?.length) return null
  const row = payload[0]?.payload
  if (!row) return null
  return (
    <div className="rounded-xl border border-[var(--aal-line)] bg-[var(--aal-card)] px-3 py-2 text-xs shadow-sm">
      <p className="font-semibold text-[var(--aal-ink)]">{row.label}</p>
      <p className="mt-1 text-[var(--aal-muted)]">{row.km.toFixed(1)} km</p>
      {row.isCurrent ? <p className="mt-1 text-sage">Current 7-day window</p> : null}
    </div>
  )
}

export default function VolumePage() {
  const { profile } = useAuth()
  const [stats, setStats] = useState(null)
  const [context, setContext] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [focusZone, setFocusZone] = useState(null)
  const [openLearn, setOpenLearn] = useState('acwr')
  const [brief, setBrief] = useState(null)
  const [briefLoading, setBriefLoading] = useState(false)
  const [briefError, setBriefError] = useState('')
  const [consented, setConsented] = useState(false)

  const loadBrief = useCallback(async (force = false) => {
    setBriefLoading(true)
    setBriefError('')
    try {
      setBrief(await getWeekBrief({ refresh: Boolean(force), topic: 'volume' }))
    } catch (err) {
      setBriefError(err.message || "Could not load this week’s brief.")
    } finally {
      setBriefLoading(false)
    }
  }, [])

  useEffect(() => {
    if (!profile?.id) return
    let cancelled = false
    async function boot() {
      setLoading(true)
      setError('')
      try {
        const [statsResult, statusResult, contextResult] = await Promise.all([
          getAthleteStats(profile.id),
          getCoachStatus().catch(() => null),
          getCoachContext().catch(() => null),
        ])
        if (cancelled) return
        setStats(statsResult)
        setContext(contextResult)
        const aiOn = Boolean(statusResult?.ai_consent)
        setConsented(aiOn)
        if (aiOn) {
          loadBrief(false)
        } else {
          setBriefError('Turn on AI coaching in settings to get a week brief.')
        }
      } catch (err) {
        if (!cancelled) setError(err.message || 'Failed to load volume stats.')
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    boot()
    return () => {
      cancelled = true
    }
  }, [profile?.id, loadBrief])

  const story = useMemo(
    () =>
      interpretLoad({
        acwr: stats?.acwr,
        acuteKm: stats?.acute_load_km,
        chronicKm: stats?.chronic_load_km,
      }),
    [stats],
  )

  const volumeData = useMemo(() => {
    const history = stats?.weekly_volume_history || []
    return history.map((bucket, index) => ({
      label: bucket.week_label,
      km: Number(bucket.total_distance_km || 0),
      isCurrent: index === history.length - 1,
    }))
  }, [stats])

  const activeZoneId = focusZone || story.zone.id
  const activeGuide = ACWR_ZONES.find((zone) => zone.id === activeZoneId) || story.zoneGuide
  const ready = !loading && stats
  const empty = ready && !hasLoadHistory(stats)
  const fitness = context?.coros?.fitness

  return (
    <AppShell title="Volume & ACWR" fill>
      <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
        <header className="relative z-20 flex shrink-0 flex-wrap items-center justify-between gap-2 border-b border-[var(--aal-line)] bg-[var(--aal-card)]/85 px-3 py-2 backdrop-blur-sm sm:px-5">
          <div className="min-w-0 pl-10 lg:pl-0">
            <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-sage">Training</p>
            <p className="truncate text-sm font-semibold text-[var(--aal-ink)]">Volume & ACWR</p>
            <p className="truncate text-[11px] text-[var(--aal-muted)]">
              This week vs the week your body is used to
            </p>
          </div>
          <WeekAlertButton
            topic="volume"
            advice={brief}
            loading={briefLoading && !brief}
            error={briefError}
            onRefresh={() => (consented ? loadBrief(true) : null)}
            refreshing={briefLoading}
            health={context?.coros?.latest_health}
            fitness={fitness}
            load={{
              acwr: stats?.acwr,
              acuteKm: stats?.acute_load_km,
              chronicKm: stats?.chronic_load_km,
            }}
          />
        </header>

        {error ? (
          <p className="shrink-0 border-b border-red-200/60 bg-red-50/80 px-4 py-2 text-sm text-danger-muted">
            {error}
          </p>
        ) : null}

        {loading ? (
          <div className="flex min-h-0 flex-1 items-center justify-center">
            <LoadingDots label="Loading volume…" />
          </div>
        ) : ready ? (
          <div className="min-h-0 flex-1 overflow-y-auto px-4 py-6 sm:px-6 lg:px-8">
        <motion.div
          className="space-y-8"
          variants={staggerContainer}
          initial="hidden"
          animate="visible"
        >
          {empty ? (
            <motion.div variants={staggerItem}>
              <EmptyState
                title="No distance in the last eight weeks"
                description="Sync Strava or COROS so activities show up here. The ratio needs a 28-day usual week before it can warn you about spikes."
                actionLabel="Open activities"
                actionTo="/activities"
              />
            </motion.div>
          ) : null}

          <motion.div variants={staggerItem} className="grid gap-6 xl:grid-cols-5">
            <SectionCard
              className="xl:col-span-3"
              title="The ratio"
              subtitle="This week’s kilometres divided by the week your body is used to."
            >
              <LoadEquation
                mobileHint="This week ÷ usual week = ACWR"
                acuteKm={stats.acute_load_km}
                chronicKm={stats.chronic_load_km}
                acwr={stats.acwr}
              />
              <div className="mt-6">
                <AcwrZoneStrip acwr={stats.acwr} activeId={activeZoneId} onSelect={setFocusZone} />
              </div>
              {activeGuide ? (
                <p className="mt-4 text-sm leading-relaxed text-[var(--aal-muted)]">
                  <span className="font-semibold text-[var(--aal-ink)]">{activeGuide.label}. </span>
                  {activeGuide.meaning}
                </p>
              ) : null}
              {isSparseBaseline(stats) && stats.acwr != null ? (
                <p className="mt-3 text-sm leading-relaxed text-[var(--aal-ink)]/80">
                  The usual-week number is still forming (fewer than three weeks with
                  distance). A high ratio here often means a thin baseline, not that you
                  trained recklessly.
                </p>
              ) : null}
            </SectionCard>

            <SectionCard
              className="xl:col-span-2"
              title="Gauge"
              subtitle="Same number, 0–2 scale. Sweet spot sits in the middle."
            >
              <ACWRGauge acwr={stats.acwr} embedded />
            </SectionCard>
          </motion.div>

          <motion.div variants={staggerItem}>
            <SectionCard
              title="Eight weeks of distance"
              subtitle="Bars are weekly kilometres. The line is your usual week (28-day average). A bar far above that line is a jump."
            >
              {volumeData.some((row) => row.km > 0) ? (
                <div className="h-72">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={volumeData} margin={{ top: 12, right: 8, left: 0, bottom: 0 }}>
                      <CartesianGrid stroke="var(--aal-line)" strokeDasharray="3 3" vertical={false} />
                      <XAxis
                        dataKey="label"
                        tick={{ fontSize: 12, fill: 'var(--aal-muted)' }}
                        axisLine={false}
                        tickLine={false}
                      />
                      <YAxis
                        tick={{ fontSize: 12, fill: 'var(--aal-muted)' }}
                        axisLine={false}
                        tickLine={false}
                        width={40}
                        tickFormatter={(value) => `${value}`}
                      />
                      <Tooltip cursor={{ fill: 'transparent' }} content={<VolumeTooltip />} />
                      {Number(stats.chronic_load_km || 0) > 0 ? (
                        <ReferenceLine
                          y={Number(stats.chronic_load_km)}
                          stroke="var(--aal-muted)"
                          strokeDasharray="4 4"
                          label={{
                            value: 'Usual week',
                            position: 'insideTopRight',
                            fill: 'var(--aal-muted)',
                            fontSize: 11,
                          }}
                        />
                      ) : null}
                      <Bar dataKey="km" radius={[6, 6, 0, 0]} activeBar={BarActiveGlow} maxBarSize={42}>
                        {volumeData.map((row) => (
                          <Cell
                            key={row.label}
                            fill={row.isCurrent ? '#8fb5a3' : '#6b9080'}
                            fillOpacity={row.km === 0 ? 0.35 : 1}
                          />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              ) : (
                <p className="py-10 text-sm text-[var(--aal-muted)]">No weekly distance to plot yet.</p>
              )}
            </SectionCard>
          </motion.div>

          <motion.section variants={staggerItem}>
            <h2 className="text-lg font-semibold text-[var(--aal-ink)]">What this means for workouts</h2>
            <p className="mt-1 max-w-2xl text-sm text-[var(--aal-muted)]">
              Tap a zone on the strip, or read your current one. Intensity and volume are separate —
              “safe” kilometres can still hide a nasty interval spike.
            </p>
            <div className="mt-4 grid gap-3 md:grid-cols-2">
              {ACWR_ZONES.map((zone) => {
                const current = zone.id === activeZoneId
                return (
                  <button
                    key={zone.id}
                    type="button"
                    onClick={() => setFocusZone(zone.id)}
                    className={`rounded-2xl border p-4 text-left transition ${
                      current
                        ? 'border-[var(--aal-ink)]/20 bg-[var(--aal-card)] shadow-sm'
                        : 'border-[var(--aal-line)] bg-[var(--aal-card)]/60 opacity-80 hover:opacity-100'
                    }`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <p className="text-sm font-semibold text-[var(--aal-ink)]">{zone.label}</p>
                      <span className="text-[10px] font-medium uppercase tracking-[0.14em] text-[var(--aal-muted)]">
                        {zone.range}
                      </span>
                    </div>
                    <p className="mt-2 text-sm leading-relaxed text-[var(--aal-muted)]">{zone.workouts}</p>
                    <p className="mt-3 text-sm leading-relaxed text-[var(--aal-ink)]/80">
                      <span className="font-semibold">Make it better. </span>
                      {zone.improve}
                    </p>
                  </button>
                )
              })}
            </div>
          </motion.section>

          <motion.section
            variants={staggerItem}
            className="rounded-2xl border border-[var(--aal-line)] bg-[var(--aal-card)] px-5 sm:px-6"
          >
            <div className="pt-5">
              <h2 className="text-lg font-semibold text-[var(--aal-ink)]">The science, without the jargon</h2>
              <p className="mt-1 text-sm text-[var(--aal-muted)]">
                Short answers first, then the papers. This is a traffic light for how fast distance is
                changing — not a fitness score and not medical advice.
              </p>
            </div>
            {LOAD_LEARN.map((topic) => (
              <LearnRow
                key={topic.id}
                topic={topic}
                open={openLearn === topic.id}
                onToggle={() => setOpenLearn((current) => (current === topic.id ? null : topic.id))}
              />
            ))}
          </motion.section>

          <motion.p variants={staggerItem} className="text-sm text-[var(--aal-muted)]">
            This page is distance from synced activities. For COROS effort-based load (short vs long
            training stress), see{' '}
            <Link to="/training/load" className="font-medium text-[var(--aal-link)]">
              Training Load
            </Link>
            .
          </motion.p>
        </motion.div>
          </div>
        ) : null}
      </div>
    </AppShell>
  )
}
