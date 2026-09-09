import { CalendarRange, ChevronRight, Gauge } from 'lucide-react'

const STEPS = [
  {
    n: 1,
    title: 'A-race is set',
    body: 'Your goal event anchors every phase — Base through Taper.',
  },
  {
    n: 2,
    title: 'Generate your roadmap',
    body: 'We count backward from race day and slot recovery weeks automatically.',
  },
  {
    n: 3,
    title: 'Plan week by week',
    body: 'Use Coach to turn each week into sessions that match the phase.',
  },
]

export default function SeasonOnboarding({ aRace, raceWeeks, generating, onGenerate }) {
  return (
    <div className="overflow-hidden rounded-2xl border border-[var(--aal-line)] bg-[var(--aal-card)]">
      <div className="border-b border-[var(--aal-line)] px-5 py-4 sm:px-6">
        <div className="flex items-start gap-3">
          <CalendarRange className="mt-0.5 h-5 w-5 shrink-0 text-indigo-500" />
          <div>
            <h2 className="text-lg font-semibold text-[var(--aal-ink)]">
              Ready to map your season
            </h2>
            <p className="mt-1 text-sm leading-relaxed text-[var(--aal-muted)]">
              About {raceWeeks != null ? `${raceWeeks} weeks` : 'several weeks'} until{' '}
              <span className="font-medium text-[var(--aal-ink)]">{aRace?.name}</span>. Three steps
              and you will have a clear roadmap.
            </p>
          </div>
        </div>
      </div>

      <ol className="divide-y divide-[var(--aal-line)]">
        {STEPS.map((step) => (
          <li key={step.n} className="flex gap-4 px-5 py-4 sm:px-6">
            <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-indigo-600/12 text-sm font-bold text-indigo-600 dark:text-indigo-300">
              {step.n}
            </span>
            <div>
              <p className="font-semibold text-[var(--aal-ink)]">{step.title}</p>
              <p className="mt-0.5 text-sm text-[var(--aal-muted)]">{step.body}</p>
            </div>
          </li>
        ))}
      </ol>

      <div className="border-t border-[var(--aal-line)] bg-indigo-500/[0.04] px-5 py-4 sm:px-6">
        <button
          type="button"
          onClick={onGenerate}
          disabled={generating}
          className="inline-flex w-full items-center justify-center gap-2 rounded-xl bg-indigo-600 px-4 py-3 text-sm font-semibold text-white transition hover:bg-indigo-500 disabled:opacity-60 sm:w-auto"
        >
          <Gauge className={`h-4 w-4 ${generating ? 'animate-spin' : ''}`} />
          {generating ? 'Building roadmap…' : 'Generate season roadmap'}
          <ChevronRight className="h-4 w-4 opacity-80" />
        </button>
        <p className="mt-2 text-xs text-[var(--aal-muted)]">
          Add B/C races on Profile first if you have them — they change how weeks are shared.
        </p>
      </div>
    </div>
  )
}
