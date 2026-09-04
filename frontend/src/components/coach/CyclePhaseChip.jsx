import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { getCycleContext } from '../../api/cycle'

const PHASE_LABELS = {
  menstrual: 'Menstrual',
  follicular: 'Follicular',
  ovulatory: 'Ovulatory',
  luteal: 'Luteal',
  late_luteal: 'Late luteal',
}

export default function CyclePhaseChip({ compact = false }) {
  const [cycle, setCycle] = useState(null)

  useEffect(() => {
    let cancelled = false
    async function load() {
      try {
        const result = await getCycleContext()
        if (!cancelled) setCycle(result)
      } catch {
        if (!cancelled) setCycle(null)
      }
    }
    load()
    return () => {
      cancelled = true
    }
  }, [])

  if (!cycle?.enabled || !cycle?.available) return null

  const label = PHASE_LABELS[cycle.phase] || cycle.phase
  const detail = `Day ${cycle.day_in_cycle} · ${cycle.cycle_length}d cycle`

  if (compact) {
    return (
      <Link
        to="/profile#profile-health"
        className="inline-flex items-center gap-2 rounded-xl border border-pink-300/40 bg-pink-50/70 px-3 py-2 text-sm font-semibold text-pink-700 transition hover:opacity-90 dark:border-pink-900/40 dark:bg-pink-950/30 dark:text-pink-200"
        title={cycle.training_note}
      >
        <span>{label}</span>
        <span className="text-[11px] font-medium opacity-80">{detail}</span>
      </Link>
    )
  }

  return (
    <div className="rounded-xl border border-pink-300/35 bg-pink-50/60 px-3 py-2 dark:border-pink-900/35 dark:bg-pink-950/25">
      <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-pink-600 dark:text-pink-300">
        Cycle phase
      </p>
      <p className="mt-0.5 text-sm font-semibold text-[var(--aal-ink)]">
        {label} · {detail}
      </p>
      {cycle.training_note ? (
        <p className="mt-1 text-xs text-[var(--aal-muted)]">{cycle.training_note}</p>
      ) : null}
    </div>
  )
}
