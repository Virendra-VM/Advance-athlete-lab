import { useEffect } from 'react'
import { motion } from 'framer-motion'
import { useAuth } from '../context/AuthContext'
import { backfillActivityMetadata } from '../api/activities'
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

  useEffect(() => {
    if (!profile?.id) return
    backfillActivityMetadata(profile.id).catch(() => {})
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
            <DailyGlance athleteProfileId={profile.id} />
            <ActivityHistory athleteProfileId={profile.id} />
          </motion.section>
        </motion.div>
      </main>
    </div>
  )
}
