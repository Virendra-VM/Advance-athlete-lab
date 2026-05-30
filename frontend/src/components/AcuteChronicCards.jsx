import MetricCard from './ui/MetricCard'

export default function AcuteChronicCards({ acuteLoadKm, chronicLoadKm }) {
  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-2">
      <MetricCard
        label="Acute Load"
        value={`${acuteLoadKm.toFixed(1)} km`}
        subtitle="Total distance in the last 7 days"
      />
      <MetricCard
        label="Chronic Load"
        value={`${chronicLoadKm.toFixed(1)} km`}
        subtitle="Average weekly distance over the last 28 days"
      />
    </div>
  )
}
