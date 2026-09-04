import { useEffect, useState } from 'react'
import { motion, useMotionValueEvent, useSpring } from 'framer-motion'
import { HRV_SCALE, getHrvZone } from '../../utils/hrvGuides'

const ARC_LENGTH = 251.2

function gaugeAngle(ratio) {
  if (ratio == null) return 0
  const clamped = Math.min(Math.max(Number(ratio), HRV_SCALE.min), HRV_SCALE.max)
  return ((clamped - HRV_SCALE.min) / (HRV_SCALE.max - HRV_SCALE.min)) * 180
}

function AnimatedRatio({ ratio }) {
  const spring = useSpring(0, { stiffness: 60, damping: 15 })
  const [display, setDisplay] = useState('0.00')

  useMotionValueEvent(spring, 'change', (value) => {
    setDisplay(value.toFixed(2))
  })

  useEffect(() => {
    spring.set(ratio ?? 0)
  }, [ratio, spring])

  if (ratio == null) {
    return <span className="text-4xl font-bold text-slate-500">—</span>
  }
  return <span className="text-4xl font-bold">{display}</span>
}

export default function HrvGauge({ ratio, assessment, title = 'Vs usual' }) {
  const zone = getHrvZone(ratio, assessment)
  const dashLength = (gaugeAngle(ratio) / 180) * ARC_LENGTH
  const color = zone.color || '#14B8A6'

  return (
    <div className="flex h-full flex-col items-center justify-center p-2">
      <p className="text-xs font-semibold uppercase tracking-widest text-indigo-500 dark:text-indigo-300">
        {title}
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
            stroke={color}
            strokeWidth="14"
            strokeLinecap="round"
            initial={{ strokeDasharray: `0 ${ARC_LENGTH}` }}
            animate={{ strokeDasharray: `${dashLength} ${ARC_LENGTH}` }}
            transition={{ duration: 1.2, ease: 'easeOut' }}
          />
        </svg>
        <div className="absolute inset-x-0 bottom-0 text-center" style={{ color }}>
          <AnimatedRatio ratio={ratio} />
        </div>
      </div>
      <span
        className="mt-3 rounded-full px-3 py-1 text-sm font-medium"
        style={{ backgroundColor: `${color}22`, color }}
      >
        {zone.label}
      </span>
    </div>
  )
}
