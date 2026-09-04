import { ChevronDown, ExternalLink } from 'lucide-react'

export default function LearnRow({ topic, open, onToggle }) {
  const paragraphs = Array.isArray(topic.body) ? topic.body : [topic.body].filter(Boolean)
  const refs = topic.refs || []

  return (
    <div className="border-b border-[var(--aal-line)] last:border-b-0">
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={open}
        className="flex w-full items-center justify-between gap-4 py-4 text-left"
      >
        <span className="text-sm font-semibold text-[var(--aal-ink)]">{topic.title}</span>
        <ChevronDown
          className={`h-4 w-4 shrink-0 text-[var(--aal-muted)] transition ${open ? 'rotate-180' : ''}`}
        />
      </button>
      {open ? (
        <div className="pb-4">
          <div className="space-y-3">
            {paragraphs.map((paragraph, index) => (
              <p key={index} className="text-sm leading-relaxed text-[var(--aal-muted)]">
                {paragraph}
              </p>
            ))}
          </div>
          {refs.length ? (
            <ul className="mt-3 space-y-1.5">
              {refs.map((ref) => (
                <li key={ref.href}>
                  <a
                    href={ref.href}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-start gap-1.5 text-sm font-medium text-[var(--aal-link)] hover:underline"
                  >
                    <ExternalLink className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                    <span>
                      {ref.label}
                      {ref.note ? (
                        <span className="font-normal text-[var(--aal-muted)]"> — {ref.note}</span>
                      ) : null}
                    </span>
                  </a>
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      ) : null}
    </div>
  )
}
