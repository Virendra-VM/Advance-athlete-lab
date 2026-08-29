import MetricCard from './ui/MetricCard'

function formatNumber(value, digits = 1) {
  if (value == null || Number.isNaN(Number(value))) return '—'
  return Number(value).toFixed(digits)
}

function raceLabel(predictions, key) {
  const value = predictions?.[key]
  if (value == null || value === '') return '—'
  return String(value)
}

export default function CorosFitnessPanel({ fitness }) {
  const preds = fitness?.race_predictions || {}

  return (
    <section className="space-y-4">
      <div>
        <h2 className="text-2xl font-bold text-slate-900 dark:text-white">Fitness & Race Form</h2>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          VO2max, threshold pace, and COROS race predictions.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        <MetricCard label="VO2max" value={formatNumber(fitness?.vo2max, 1)} subtitle="ml/kg/min" />
        <MetricCard
          label="Threshold pace"
          value={fitness?.threshold_pace || '—'}
          subtitle="Lactate / threshold pace"
        />
        <MetricCard
          label="Running performance"
          value={formatNumber(fitness?.running_performance, 0)}
          subtitle="COROS running level"
        />
        <MetricCard label="5K prediction" value={raceLabel(preds, '5k')} />
        <MetricCard label="10K prediction" value={raceLabel(preds, '10k')} />
        <MetricCard label="Half / Marathon" value={`${raceLabel(preds, 'half')} / ${raceLabel(preds, 'marathon')}`} />
      </div>
    </section>
  )
}
