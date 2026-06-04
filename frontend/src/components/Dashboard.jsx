import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { useAuth } from '../context/AuthContext'
import { backfillActivityMetadata, listActivities } from '../api/activities'
import {
  getStravaConnectionStatus,
  getStravaSyncStatus,
  startStravaSync,
} from '../api/strava'
import {
  pagePaddingClass,
  pageShellClass,
  staggerContainer,
  staggerItem,
} from '../utils/statusColors'
import ActivityHistory from './ActivityHistory'
import DailyGlance from './DailyGlance'
import Navigation from './Navigation'

export default function Dashboard() {
  const { profile } = useAuth()
  const [refreshKey, setRefreshKey] = useState(0)

  useEffect(() => {
    if (!profile?.id) return
    backfillActivityMetadata(profile.id).catch(() => {})
  }, [profile?.id])

  useEffect(() => {
    if (!profile?.id) return

    let cancelled = false
    let pollTimer

    async function pollUntilSyncDone() {
      if (cancelled) return
      const current = await getStravaSyncStatus()
      if (!current.running) {
        setRefreshKey((value) => value + 1)
        return
      }
      pollTimer = window.setTimeout(pollUntilSyncDone, 2000)
    }

    async function ensureStravaActivitiesSynced() {
      try {
        const status = await getStravaConnectionStatus(profile.id)
        if (!status.connected || cancelled) return

        const syncStatus = await getStravaSyncStatus()
        if (syncStatus.running) {
          await pollUntilSyncDone()
          return
        }

        const activities = await listActivities(profile.id)
        if (activities.length > 0 || cancelled) return

        try {
          await startStravaSync(profile.id)
        } catch (err) {
          if (!String(err.message || '').includes('409')) throw err
        }
        await pollUntilSyncDone()
      } catch {
        // Strava may be disconnected or sync already handled on callback.
      }
    }

    ensureStravaActivitiesSynced()
    return () => {
      cancelled = true
      if (pollTimer) window.clearTimeout(pollTimer)
    }
  }, [profile?.id])

  if (!profile) {
    return (
      <div className={pageShellClass}>
        <Navigation subtitle="Athlete Dashboard" />
        <main className={pagePaddingClass}>Loading profile...</main>
      </div>
    )
  }

  return (
    <div className={pageShellClass}>
      <Navigation subtitle="Athlete Dashboard" />

      <main className={pagePaddingClass}>
        <motion.div
          variants={staggerContainer}
          initial="hidden"
          animate="visible"
          className="space-y-8"
        >
          <motion.section variants={staggerItem} className="space-y-8">
            <DailyGlance athleteProfileId={profile.id} refreshKey={refreshKey} />
            <ActivityHistory athleteProfileId={profile.id} refreshKey={refreshKey} />
          </motion.section>
        </motion.div>
      </main>
    </div>
  )
}
