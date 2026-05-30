import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { useMotionValueEvent, useSpring } from 'framer-motion'
import Card from './ui/Card'
import { getAcwrZone } from '../utils/statusColors'

const ARC_LENGTH = 251.2

function gaugeAngle(acwr) {
  if (acwr == null) return 0
  return (Math.min(Math.max(acwr, 0), 2) / 2) * 180
}

function AnimatedAcwrValue({ acwr, className }) {
  const spring = useSpring(0, { stiffness: 60, damping: 15 })
  const [display, setDisplay] = useState('0.00')

  useMotionValueEvent(spring, 'change', (value) => {
    setDisplay(value.toFixed(2))
  })

  useEffect(() => {
    spring.set(acwr ?? 0)
  }, [acwr, spring])

  if (acwr == null) {
    return <span className={`text-4xl font-bold text-slate-500 ${className}`}>—</span>
  }

  return <span className={`text-4xl font-bold ${className}`}>{display}</span>
}

export default function ACWRGauge({ acwr }) {
  const zone = getAcwrZone(acwr)
  const dashLength = (gaugeAngle(acwr) / 180) * ARC_LENGTH

  return (
    <Card className="flex h-full flex-col items-center justify-center p-6">
      <p className="text-xs font-semibold uppercase tracking-widest text-slate-500 dark:text-slate-400">
        ACWR
      </p>
      <div className="relative mt-4 h-28 w-48">
        <svg viewBox="0 0 200 110" className="h-full w-full">
          <path
            d="M 20 100 A 80 80 0 0 1 180 100"
            fill="none"
            stroke="currentColor"
            className="text-slate-200 dark:text-gray-700"
            strokeWidth="14"
            strokeLinecap="round"
          />
          <motion.path
            d="M 20 100 A 80 80 0 0 1 180 100"
            fill="none"
            stroke={zone.gaugeColor}
            strokeWidth="14"
            strokeLinecap="round"
            initial={{ strokeDasharray: `0 ${ARC_LENGTH}` }}
            animate={{ strokeDasharray: `${dashLength} ${ARC_LENGTH}` }}
            transition={{ duration: 1.2, ease: 'easeOut' }}
          />
        </svg>
        <div className={`absolute inset-x-0 bottom-0 text-center ${zone.textClass}`}>
          <AnimatedAcwrValue acwr={acwr} />
        </div>
      </div>
      <span className={`mt-3 rounded-full px-3 py-1 text-sm font-medium ${zone.badgeClass}`}>
        {zone.label}
      </span>
    </Card>
  )
}
