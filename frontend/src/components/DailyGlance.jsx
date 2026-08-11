import { useCallback, useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { getAthleteStats } from '../api/athlete'
import { listActivities } from '../api/activities'
import { cardShellClass, staggerContainer } from '../utils/statusColors'
import ACWRGauge from './ACWRGauge'
import AcuteChronicCards from './AcuteChronicCards'
import ActivityOverview from './ActivityOverview'
import WeeklyVolumeChart from './WeeklyVolumeChart'

export default function DailyGlance({ athleteProfileId, refreshKey = 0 }) {
  const [stats, setStats] = useState(null)
  const [activities, setActivities] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const loadData = useCallback(async () => {
    if (!athleteProfileId) return

    setLoading(true)
    setError('')

    try {
      const [statsData, activityPage] = await Promise.all([
        getAthleteStats(athleteProfileId),
        listActivities(athleteProfileId, { page: 1, page_size: 100 }),
      ])
      setStats(statsData)
      setActivities(activityPage.items || [])
    } catch (err) {
      setError(err.message || 'Failed to load training load data.')
    } finally {
      setLoading(false)
    }
  }, [athleteProfileId])

  useEffect(() => {
    loadData()
  }, [loadData, refreshKey])

  if (loading) {
    return (
      <section className={`p-8 text-center text-slate-500 dark:text-slate-400 ${cardShellClass}`}>
        Loading training load...
      </section>
    )
  }

  if (error) {
    return (
      <section className="rounded-2xl border border-danger-muted/30 bg-red-50 p-6 text-danger-muted dark:bg-red-950/30">
        {error}
      </section>
    )
  }

  return (
    <motion.section
      variants={staggerContainer}
      initial="hidden"
      animate="visible"
      className="space-y-8"
    >
      <ActivityOverview activities={activities} />

      <div>
        <h2 className="text-2xl font-bold text-slate-900 dark:text-white">Daily Glance</h2>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          Training load metrics based on your imported activity history.
        </p>
      </div>

      <AcuteChronicCards acuteLoadKm={stats.acute_load_km} chronicLoadKm={stats.chronic_load_km} />

      <div className="grid gap-4 xl:grid-cols-3">
        <div className="xl:col-span-1">
          <ACWRGauge acwr={stats.acwr} />
        </div>
        <div className="xl:col-span-2">
          <WeeklyVolumeChart activities={activities} />
        </div>
      </div>
    </motion.section>
  )
}
