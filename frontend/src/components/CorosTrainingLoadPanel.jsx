import MetricCard from './ui/MetricCard'
import Card from './ui/Card'

function formatNumber(value, digits = 1) {
  if (value == null || Number.isNaN(Number(value))) return '—'
  return Number(value).toFixed(digits)
}

export default function CorosTrainingLoadPanel({ trainingLoad }) {
  const comments = Array.isArray(trainingLoad?.daily_comments)
    ? trainingLoad.daily_comments
    : []

  return (
    <section className="space-y-4">
      <div>
        <h2 className="text-2xl font-bold text-slate-900 dark:text-white">COROS Training Load</h2>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          Official short-term / long-term load and daily comments from COROS.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        <MetricCard label="Short-term load" value={formatNumber(trainingLoad?.short_load, 0)} />
        <MetricCard label="Long-term load" value={formatNumber(trainingLoad?.long_load, 0)} />
        <MetricCard label="Load ratio" value={formatNumber(trainingLoad?.load_ratio, 2)} />
      </div>

      {comments.length > 0 && (
        <Card className="space-y-3 p-6">
          <h3 className="text-sm font-semibold uppercase tracking-widest text-slate-500">
            Daily comments
          </h3>
          <ul className="space-y-2 text-sm text-slate-700 dark:text-slate-300">
            {comments.slice(0, 7).map((comment, index) => (
              <li key={index} className="rounded-xl bg-slate-50 px-3 py-2 dark:bg-white/5">
                {typeof comment === 'string'
                  ? comment
                  : comment?.comment || comment?.text || JSON.stringify(comment)}
              </li>
            ))}
          </ul>
        </Card>
      )}
    </section>
  )
}
