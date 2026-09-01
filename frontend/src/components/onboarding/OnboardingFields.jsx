import { X } from 'lucide-react'
import {
  BODY_REGIONS,
  EXPERIENCE_LEVELS,
  INJURY_SEVERITY_OPTIONS,
  INJURY_STATUS_OPTIONS,
  SPORT_OPTIONS,
  VOLUME_UNIT_BY_SPORT,
  primarySports,
} from '../../utils/onboardingSteps'

const inputClass =
  'mt-2 w-full rounded-xl border border-[var(--aal-line)] bg-[var(--aal-card)] px-4 py-3 text-[var(--aal-ink)] outline-none ring-sage focus:ring-2'

function normalizeOption(option) {
  if (option != null && typeof option === 'object') return option
  return { value: option, label: String(option) }
}

export function Chip({ label, selected, onClick, size = 'md' }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-full border font-medium transition-colors ${
        size === 'sm' ? 'px-3 py-1.5 text-xs' : 'px-4 py-2 text-sm'
      } ${
        selected
          ? 'border-sage bg-sage text-white'
          : 'border-[var(--aal-line)] bg-[var(--aal-card)] text-[var(--aal-ink)] hover:border-sage/60'
      }`}
    >
      {label}
    </button>
  )
}

function FieldShell({ label, help, required, children }) {
  return (
    <div className="min-w-0">
      {label && (
        <span className="text-xs font-semibold uppercase tracking-wide text-[var(--aal-muted)]">
          {label}
          {required && <span className="ml-1 text-sage">*</span>}
        </span>
      )}
      {children}
      {help && <p className="mt-2 text-xs text-[var(--aal-muted)]">{help}</p>}
    </div>
  )
}

function SportsField({ value = [], onChange }) {
  const selected = value || []

  function toggleSport(sport) {
    const exists = selected.some((entry) => entry.sport === sport)
    if (exists) {
      onChange(selected.filter((entry) => entry.sport !== sport))
      return
    }
    onChange([...selected, { sport, priority: 'primary', experience_level: 'Beginner' }])
  }

  function updateEntry(sport, patch) {
    onChange(selected.map((entry) => (entry.sport === sport ? { ...entry, ...patch } : entry)))
  }

  return (
    <div>
      <div className="flex flex-wrap gap-2">
        {SPORT_OPTIONS.map((sport) => (
          <Chip
            key={sport}
            label={sport}
            selected={selected.some((entry) => entry.sport === sport)}
            onClick={() => toggleSport(sport)}
          />
        ))}
      </div>

      {selected.length > 0 && (
        <div className="mt-6 space-y-3">
          {selected.map((entry) => (
            <div
              key={entry.sport}
              className="rounded-xl border border-[var(--aal-line)] bg-[var(--aal-card)] p-4"
            >
              <div className="flex items-center justify-between gap-3">
                <p className="font-semibold">{entry.sport}</p>
                <button
                  type="button"
                  onClick={() => toggleSport(entry.sport)}
                  className="rounded-lg p-1 text-[var(--aal-muted)] hover:text-danger-muted"
                  aria-label={`Remove ${entry.sport}`}
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
              <div className="mt-3 grid gap-3 sm:grid-cols-2">
                <label className="block">
                  <span className="text-xs font-semibold uppercase tracking-wide text-[var(--aal-muted)]">
                    Experience
                  </span>
                  <select
                    value={entry.experience_level || ''}
                    onChange={(e) => updateEntry(entry.sport, { experience_level: e.target.value })}
                    className={inputClass}
                  >
                    {EXPERIENCE_LEVELS.map((level) => (
                      <option key={level} value={level}>
                        {level}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="block">
                  <span className="text-xs font-semibold uppercase tracking-wide text-[var(--aal-muted)]">
                    Priority
                  </span>
                  <select
                    value={entry.priority || 'primary'}
                    onChange={(e) => updateEntry(entry.sport, { priority: e.target.value })}
                    className={inputClass}
                  >
                    <option value="primary">Main sport</option>
                    <option value="secondary">Supporting</option>
                  </select>
                </label>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function WeeklyVolumeField({ value = {}, onChange, answers }) {
  const sports = primarySports(answers)
  if (sports.length === 0) {
    return (
      <p className="text-sm text-[var(--aal-muted)]">
          Pick your sports first to log current weekly volume.
      </p>
    )
  }

  return (
    <div className="grid gap-3 sm:grid-cols-2">
      {sports.map((entry) => (
        <label key={entry.sport} className="block">
          <span className="text-xs font-semibold uppercase tracking-wide text-[var(--aal-muted)]">
            {entry.sport}
          </span>
          <span className="ml-1 text-xs normal-case text-[var(--aal-muted)]">
            · {VOLUME_UNIT_BY_SPORT[entry.sport] || 'per week'}
          </span>
          <input
            type="number"
            min="0"
            value={value?.[entry.sport] ?? ''}
            onChange={(e) => onChange({ ...(value || {}), [entry.sport]: e.target.value })}
            className={inputClass}
            placeholder="0"
          />
        </label>
      ))}
    </div>
  )
}

function InjuriesField({ value = [], onChange }) {
  const injuries = value || []

  function addInjury(region) {
    if (injuries.some((entry) => entry.body_region === region)) return
    onChange([...injuries, { body_region: region, status: 'past', severity: 'mild', notes: '' }])
  }

  function removeInjury(region) {
    onChange(injuries.filter((entry) => entry.body_region !== region))
  }

  function updateInjury(region, patch) {
    onChange(
      injuries.map((entry) =>
        entry.body_region === region ? { ...entry, ...patch } : entry,
      ),
    )
  }

  return (
    <div>
      <div className="flex flex-wrap gap-2">
        {BODY_REGIONS.map((region) => (
          <Chip
            key={region}
            label={region}
            selected={injuries.some((entry) => entry.body_region === region)}
            onClick={() =>
              injuries.some((entry) => entry.body_region === region)
                ? removeInjury(region)
                : addInjury(region)
            }
          />
        ))}
      </div>

      {injuries.length > 0 && (
        <div className="mt-6 space-y-3">
          {injuries.map((entry) => (
            <div
              key={entry.body_region}
              className="rounded-xl border border-[var(--aal-line)] bg-[var(--aal-card)] p-4"
            >
              <div className="flex items-center justify-between gap-3">
                <p className="font-semibold">{entry.body_region}</p>
                <button
                  type="button"
                  onClick={() => removeInjury(entry.body_region)}
                  className="rounded-lg p-1 text-[var(--aal-muted)] hover:text-danger-muted"
                  aria-label={`Remove ${entry.body_region}`}
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
              <div className="mt-3 grid gap-3 sm:grid-cols-2">
                <label className="block">
                  <span className="text-xs font-semibold uppercase tracking-wide text-[var(--aal-muted)]">
                    Status
                  </span>
                  <select
                    value={entry.status || 'past'}
                    onChange={(e) => updateInjury(entry.body_region, { status: e.target.value })}
                    className={inputClass}
                  >
                    {INJURY_STATUS_OPTIONS.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="block">
                  <span className="text-xs font-semibold uppercase tracking-wide text-[var(--aal-muted)]">
                    Severity
                  </span>
                  <select
                    value={entry.severity || 'mild'}
                    onChange={(e) => updateInjury(entry.body_region, { severity: e.target.value })}
                    className={inputClass}
                  >
                    {INJURY_SEVERITY_OPTIONS.map((level) => (
                      <option key={level} value={level}>
                        {level}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
              <label className="mt-3 block">
                <span className="text-xs font-semibold uppercase tracking-wide text-[var(--aal-muted)]">
                  Detail (optional)
                </span>
                <input
                  value={entry.notes || ''}
                  onChange={(e) => updateInjury(entry.body_region, { notes: e.target.value })}
                  placeholder="e.g. flares up after 8 km"
                  className={inputClass}
                />
              </label>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

const CONSENT_ITEMS = [
  {
    key: 'ai_coaching',
    label: 'Use my profile to generate AI coaching',
    detail: 'Required for plans, daily advice, and coach chat.',
    required: true,
  },
  {
    key: 'health_data',
    label: 'Use my wearable health data (sleep, HRV, recovery)',
    detail: 'Lets the coach adjust load when you are under-recovered.',
  },
  {
    key: 'research',
    label: 'Use anonymised data to improve coaching quality',
    detail: 'Optional. No personal identifiers leave your account.',
  },
]

export function ConsentsField({ value = {}, onChange }) {
  return (
    <div className="space-y-3">
      {CONSENT_ITEMS.map((item) => {
        const checked = Boolean(value?.[item.key])
        return (
          <label
            key={item.key}
            className="flex cursor-pointer items-start gap-3 rounded-xl border border-[var(--aal-line)] bg-[var(--aal-card)] p-4"
          >
            <input
              type="checkbox"
              checked={checked}
              onChange={(e) => onChange({ ...(value || {}), [item.key]: e.target.checked })}
              className="mt-0.5 h-4 w-4 accent-sage"
            />
            <span className="min-w-0">
              <span className="block text-sm font-semibold">
                {item.label}
                {item.required && <span className="ml-1 text-sage">*</span>}
              </span>
              <span className="mt-1 block text-xs text-[var(--aal-muted)]">{item.detail}</span>
            </span>
          </label>
        )
      })}
      <p className="text-xs text-[var(--aal-muted)]">
        Advance Athlete Lab provides coaching guidance, not medical advice. For pain, illness, or
        acute injury, see a qualified professional.
      </p>
    </div>
  )
}

function ChipsTextField({ field, value = '', onChange }) {
  const parts = String(value || '')
    .split(',')
    .map((part) => part.trim())
    .filter(Boolean)

  function toggle(option) {
    const next = parts.includes(option)
      ? parts.filter((part) => part !== option)
      : [...parts, option]
    onChange(next.join(', '))
  }

  return (
    <div>
      <input
        value={value || ''}
        onChange={(e) => onChange(e.target.value)}
        placeholder={field.placeholder || 'Type your answer'}
        className={inputClass}
      />
      <div className="mt-3 flex flex-wrap gap-2">
        {(field.options || []).map((option) => (
          <Chip
            key={option}
            size="sm"
            label={parts.includes(option) ? option : `+ ${option}`}
            selected={parts.includes(option)}
            onClick={() => toggle(option)}
          />
        ))}
      </div>
    </div>
  )
}

export default function OnboardingField({ field, answers, value, onChange }) {
  if (field.type === 'sports') {
    return (
      <FieldShell label={field.label} help={field.help} required={field.required}>
        <div className="mt-2">
          <SportsField value={value} onChange={onChange} />
        </div>
      </FieldShell>
    )
  }

  if (field.type === 'weekly-volume') {
    return (
      <FieldShell
        label="Current weekly volume"
        help="Roughly what you are doing now — not your target."
      >
        <div className="mt-2">
          <WeeklyVolumeField value={value} onChange={onChange} answers={answers} />
        </div>
      </FieldShell>
    )
  }

  if (field.type === 'injuries') {
    return (
      <FieldShell label="Injury history" help={field.help}>
        <div className="mt-2">
          <InjuriesField value={value} onChange={onChange} />
        </div>
      </FieldShell>
    )
  }

  if (field.type === 'consents') {
    return (
      <div className="mt-2">
        <ConsentsField value={value} onChange={onChange} />
      </div>
    )
  }

  if (field.type === 'chips-single') {
    const options = (field.options || []).map(normalizeOption)
    return (
      <FieldShell label={field.label} help={field.help} required={field.required}>
        <div className="mt-3 flex flex-wrap gap-2">
          {options.map((option) => (
            <Chip
              key={String(option.value)}
              label={option.label}
              selected={String(value ?? '') === String(option.value)}
              onClick={() => onChange(option.value)}
            />
          ))}
        </div>
      </FieldShell>
    )
  }

  if (field.type === 'chips-multi') {
    const selected = String(value || '')
      .split(',')
      .map((part) => part.trim())
      .filter(Boolean)
    function toggle(option) {
      const next = selected.includes(option)
        ? selected.filter((part) => part !== option)
        : [...selected, option]
      onChange(next.join(', '))
    }
    return (
      <FieldShell label={field.label} help={field.help} required={field.required}>
        <div className="mt-3 flex flex-wrap gap-2">
          {(field.options || []).map((option) => (
            <Chip
              key={option}
              label={option}
              selected={selected.includes(option)}
              onClick={() => toggle(option)}
            />
          ))}
        </div>
      </FieldShell>
    )
  }

  if (field.type === 'chips-text') {
    return (
      <FieldShell label={field.label} help={field.help} required={field.required}>
        <ChipsTextField field={field} value={value} onChange={onChange} />
      </FieldShell>
    )
  }

  if (field.type === 'textarea') {
    return (
      <FieldShell label={field.label} help={field.help} required={field.required}>
        <textarea
          rows={3}
          value={value || ''}
          onChange={(e) => onChange(e.target.value)}
          placeholder={field.placeholder || ''}
          className={inputClass}
        />
      </FieldShell>
    )
  }

  if (field.type === 'number' || field.type === 'date' || field.type === 'text') {
    const label = field.suffix ? `${field.label} (${field.suffix})` : field.label
    return (
      <FieldShell label={label} help={field.help} required={field.required}>
        <input
          type={field.type}
          value={value ?? ''}
          min={field.min}
          max={field.max}
          step={field.step}
          onChange={(e) => onChange(e.target.value)}
          placeholder={field.placeholder || ''}
          className={inputClass}
        />
      </FieldShell>
    )
  }

  return null
}
