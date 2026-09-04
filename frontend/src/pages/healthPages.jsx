import MetricPage from './MetricPage'

export function RecoveryPage() {
  return (
    <MetricPage
      theme="health"
      title="Recovery"
      description="Recovery percentage from stored COROS fitness snapshots."
      metric="recovery"
      valueSuffix="%"
      showRangeTabs={false}
    />
  )
}

export { default as SleepPage } from './SleepPage'
export { default as TrainingLoadPage } from './TrainingLoadPage'
export { default as HrvPage } from './HrvPage'
export { default as StressPage } from './StressPage'
export { default as RhrPage } from './RhrPage'
export { default as DailyHealthPage } from './DailyHealthPage'

export function FitnessPage() {
  return (
    <MetricPage
      title="Fitness"
      eyebrow="Training"
      description="VO2max from available COROS fitness snapshots."
      metric="vo2max"
      valueDigits={1}
      showRangeTabs={false}
    />
  )
}
