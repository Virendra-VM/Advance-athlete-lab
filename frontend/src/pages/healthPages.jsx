import AppShell from '../components/layout/AppShell'
import MetricPage from './MetricPage'

export function RecoveryPage() {
  return (
    <MetricPage
      title="Recovery"
      description="Recovery percentage from stored COROS fitness snapshots."
      metric="recovery"
      valueSuffix="%"
      showRangeTabs={false}
    />
  )
}

export { default as SleepPage } from './SleepPage'

export function HrvPage() {
  return (
    <MetricPage
      title="HRV"
      description="Sleep HRV averages and assessments."
      metric="hrv"
      valueSuffix=" ms"
    />
  )
}

export function StressPage() {
  return (
    <MetricPage
      title="Stress"
      description="Daily average stress from COROS."
      metric="stress"
    />
  )
}

export function RhrPage() {
  return (
    <MetricPage
      title="Resting HR"
      description="Resting heart rate trend."
      metric="rhr"
      valueSuffix=" bpm"
    />
  )
}

export function DailyHealthPage() {
  return (
    <AppShell title="Daily Health">
      <div className="space-y-10">
        <MetricPage
          bare
          title="Daily Health"
          eyebrow="Health"
          description="Steps and calories from COROS daily health."
          metric="daily"
          secondaryLabel="Steps primary · calories secondary"
          showSecondary
        />
        <MetricPage
          bare
          title="Average HR"
          eyebrow="Health"
          description="Daily average heart rate companion trend."
          metric="avg_hr"
          valueSuffix=" bpm"
        />
      </div>
    </AppShell>
  )
}

export function TrainingLoadPage() {
  return (
    <MetricPage
      title="Training Load"
      eyebrow="Training"
      description="COROS short/long load ratio from the latest sync (~1 week of daily comments)."
      metric="load"
      valueDigits={2}
      showRangeTabs={false}
    />
  )
}

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
