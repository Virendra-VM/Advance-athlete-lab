import Card from './Card'

export default function MetricCard({ label, value, subtitle, className = '' }) {
  return (
    <Card className={`p-6 ${className}`}>
      <p className="text-xs font-semibold uppercase tracking-widest text-slate-500 dark:text-slate-400">
        {label}
      </p>
      <p className="mt-3 text-4xl font-bold tracking-tight text-slate-900 dark:text-white">
        {value}
      </p>
      {subtitle && (
        <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">{subtitle}</p>
      )}
    </Card>
  )
}
