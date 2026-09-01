import { Link } from 'react-router-dom'
import { Pencil } from 'lucide-react'
import { VOLUME_UNIT_BY_SPORT } from '../../utils/onboardingSteps'
import {
  cmToInches,
  durationLabel,
  formatDate,
  formatHeight,
  formatWeight,
  historyLabel,
  inchesToCm,
  injurySummary,
  isEmptyValue,
  kgToLb,
  lbToKg,
  PROFILE_SECTIONS,
  sexLabel,
  splitList,
  unitsLabel,
  weekSummary,
} from '../../utils/profileView'

const inputClass =
  'mt-2 w-full rounded-xl border border-[var(--aal-line)] bg-[var(--aal-card)] px-4 py-3 text-[var(--aal-ink)] outline-none ring-sage focus:ring-2'

function formatEventValue(name, dateLabel) {
  const bits = [name, dateLabel].filter(Boolean)
  return bits.length ? bits.join(' · ') : null
}

export function EmptyValue() {
  return <span className="italic text-[var(--aal-muted)]">Not set</span>
}

export function DisplayValue({ children }) {
  if (children == null || children === '') return <EmptyValue />
  return children
}

/** Single profile field with the same left accent used in Health → Injuries. */
export function FactorItem({ label, children, wide = false }) {
  return (
    <div className={`border-l-2 border-sage/45 pl-4 ${wide ? 'sm:col-span-2' : ''}`}>
      <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-[var(--aal-muted)]">
        {label}
      </p>
      <div className="mt-1.5 text-[15px] leading-relaxed text-[var(--aal-ink)]">
        {children ?? <EmptyValue />}
      </div>
    </div>
  )
}

function FactorGroup({ title, subtitle, children }) {
  return (
    <div>
      {title ? (
        <div className="mb-4">
          <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-sage/90">
            {title}
          </p>
          {subtitle ? (
            <p className="mt-1 text-sm text-[var(--aal-muted)]">{subtitle}</p>
          ) : null}
        </div>
      ) : null}
      <div className="grid gap-5 sm:grid-cols-2">{children}</div>
    </div>
  )
}

function FactorSections({ groups }) {
  return (
    <div>
      {groups.map((group, index) => (
        <div key={group.key}>
          {index > 0 ? (
            <div className="my-6 border-t border-[var(--aal-line)]" role="separator" />
          ) : null}
          <FactorGroup title={group.title} subtitle={group.subtitle}>
            {group.factors}
          </FactorGroup>
        </div>
      ))}
    </div>
  )
}

function parseTextPoints(text) {
  if (isEmptyValue(text)) return []
  const raw = String(text).trim()
  let parts = raw
    .split(/\n+/)
    .map((part) => part.trim())
    .filter(Boolean)
  if (parts.length === 1) {
    const commaParts = splitList(raw)
    if (commaParts.length > 1) parts = commaParts
  }
  return parts.map((part) => part.replace(/^[-•*]\s*/, '').trim()).filter(Boolean)
}

function TextBulletPoints({ text }) {
  const items = parseTextPoints(text)
  if (!items.length) return <EmptyValue />

  return (
    <ul className="space-y-2">
      {items.map((item) => (
        <li key={item} className="flex items-start gap-2.5">
          <span
            className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-sage"
            aria-hidden
          />
          <span className="min-w-0 flex-1 text-[15px] leading-relaxed text-[var(--aal-ink)]">
            {item}
          </span>
        </li>
      ))}
    </ul>
  )
}

export function IdentityFocus({ form }) {
  const event = formatEventValue(form.goal_event_name, formatDate(form.goal_event_date))
  const target = form.goal_metric

  if (!event && isEmptyValue(target)) {
    return <p className="mt-4 italic text-[var(--aal-muted)]">No event or target set yet</p>
  }

  return (
    <div className="mt-4 grid gap-4 sm:grid-cols-2">
      <FactorItem label="Event">
        <DisplayValue>{event}</DisplayValue>
      </FactorItem>
      <FactorItem label="Target">
        <DisplayValue>{target}</DisplayValue>
      </FactorItem>
    </div>
  )
}

function WeeklyVolumePoints({ volume, sports }) {
  const entries = Object.entries(volume || {}).filter(([, value]) => !isEmptyValue(value))
  if (!entries.length) return <EmptyValue />

  const sportSet = new Set((sports || []).map((entry) => entry.sport))

  return (
    <ul className="space-y-2">
      {entries.map(([sport, value]) => {
        const unit = VOLUME_UNIT_BY_SPORT[sport] || 'per week'
        const isExtra = sportSet.size > 0 && !sportSet.has(sport)
        return (
          <li key={sport} className="flex items-start gap-2.5">
            <span
              className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-sage"
              aria-hidden
            />
            <span className="min-w-0 flex-1 text-[15px] leading-relaxed">
              <span className={`font-semibold ${isExtra ? 'text-[var(--aal-muted)]' : 'text-[var(--aal-ink)]'}`}>
                {sport}
              </span>
              <span className="mx-1.5 text-[var(--aal-muted)]">·</span>
              <span className="text-[var(--aal-ink)]">
                {value} {unit}
              </span>
            </span>
          </li>
        )
      })}
    </ul>
  )
}

export function DefinitionList({ rows }) {
  return (
    <dl className="grid gap-x-8 gap-y-5 sm:grid-cols-2">
      {rows.map((row) => (
        <div key={row.label} className={row.wide ? 'sm:col-span-2' : ''}>
          <dt className="text-[11px] font-semibold uppercase tracking-[0.16em] text-[var(--aal-muted)]">
            {row.label}
          </dt>
          <dd className="mt-1.5 text-[15px] leading-relaxed text-[var(--aal-ink)]">
            {row.node ?? <DisplayValue>{row.value}</DisplayValue>}
          </dd>
        </div>
      ))}
    </dl>
  )
}

export function SportPills({ sports = [] }) {
  if (!sports.length) return <EmptyValue />
  return (
    <div className="flex flex-wrap gap-2">
      {sports.map((entry) => (
        <span
          key={entry.sport}
          className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-semibold ${
            entry.priority === 'secondary'
              ? 'border border-[var(--aal-line)] text-[var(--aal-ink)]'
              : 'bg-sage/15 text-sage'
          }`}
        >
          {entry.sport}
          {entry.experience_level ? (
            <span className="font-medium opacity-70">· {entry.experience_level}</span>
          ) : null}
        </span>
      ))}
    </div>
  )
}

export function TextPills({ items }) {
  const list = splitList(items)
  if (!list.length) return <EmptyValue />
  return (
    <div className="flex flex-wrap gap-2">
      {list.map((item) => (
        <span
          key={item}
          className="rounded-full border border-[var(--aal-line)] px-3 py-1 text-xs font-medium"
        >
          {item}
        </span>
      ))}
    </div>
  )
}

export function FactStrip({ form }) {
  const age = form.displayAge
  const facts = [
    { label: 'Age', value: age != null ? String(age) : null },
    { label: 'Height', value: formatHeight(form.height_cm, form.units) },
    { label: 'Weight', value: formatWeight(form.weight, form.units) },
    { label: 'Week', value: weekSummary(form) },
  ]
  return (
    <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
      {facts.map((fact, index) => (
        <div
          key={fact.label}
          className={`rounded-2xl border border-[var(--aal-line)] bg-[var(--aal-card)] px-4 py-4 ${
            index === 0 ? 'border-sage/35 bg-sage/[0.04]' : ''
          }`}
        >
          <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-[var(--aal-muted)]">
            {fact.label}
          </p>
          <p className="mt-2 font-display text-2xl font-medium tracking-tight text-[var(--aal-ink)]">
            {fact.value || <span className="text-lg italic text-[var(--aal-muted)]">Not set</span>}
          </p>
        </div>
      ))}
    </div>
  )
}

export function JumpNav({ onJump }) {
  return (
    <nav
      aria-label="Profile sections"
      className="flex flex-wrap gap-1 border-b border-[var(--aal-line)] pb-1"
    >
      {PROFILE_SECTIONS.filter((section) => section.id !== 'identity').map((section) => (
        <button
          key={section.id}
          type="button"
          onClick={() => onJump(section.id)}
          className="rounded-full px-3 py-1.5 text-sm text-[var(--aal-muted)] transition hover:bg-sage/10 hover:text-[var(--aal-ink)]"
        >
          {section.label}
        </button>
      ))}
    </nav>
  )
}

export function SectionEditButton({ editing, onEdit }) {
  if (editing) {
    return (
      <span className="text-xs font-semibold uppercase tracking-[0.14em] text-sage">Editing</span>
    )
  }
  return (
    <button
      type="button"
      onClick={onEdit}
      className="inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-sm font-semibold text-[var(--aal-muted)] transition hover:bg-sage/10 hover:text-[var(--aal-ink)]"
    >
      <Pencil className="h-3.5 w-3.5" />
      Edit
    </button>
  )
}

export function MissingCompleteness({ items, onJump }) {
  if (!items.length) return null
  const preview = items.slice(0, 3)
  const extra = items.length - preview.length
  return (
    <p className="text-sm text-[var(--aal-muted)]">
      {items.length} left:{' '}
      {preview.map((item, index) => (
        <span key={item.key}>
          <button
            type="button"
            onClick={() => onJump(item)}
            className="font-medium text-sage underline decoration-dotted underline-offset-2 hover:text-[var(--aal-ink)]"
          >
            {item.label}
          </button>
          {index < preview.length - 1 ? ', ' : ''}
        </span>
      ))}
      {extra > 0 ? ` +${extra} more` : null}
    </p>
  )
}

export function StickySaveBar({ dirty, saving, message, error, onDone, onDiscard }) {
  return (
    <div className="sticky bottom-4 z-20">
      <div className="flex flex-col gap-3 rounded-2xl border border-[var(--aal-line)] bg-[var(--aal-card)]/95 px-4 py-3 backdrop-blur sm:flex-row sm:items-center sm:justify-between">
        <div className="min-w-0">
          {error ? (
            <p className="text-sm text-danger-muted">{error}</p>
          ) : message ? (
            <p className="text-sm text-sage">{message}</p>
          ) : (
            <p className="text-sm text-[var(--aal-muted)]">
              {dirty ? 'You have unsaved changes.' : 'Editing profile — nothing to save yet.'}
            </p>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {dirty ? (
            <button
              type="button"
              onClick={onDiscard}
              className="rounded-xl border border-[var(--aal-line)] px-4 py-2.5 text-sm font-semibold hover:bg-[var(--aal-bg)]"
            >
              Discard
            </button>
          ) : (
            <button
              type="button"
              onClick={onDone}
              className="rounded-xl border border-[var(--aal-line)] px-4 py-2.5 text-sm font-semibold hover:bg-[var(--aal-bg)]"
            >
              Done
            </button>
          )}
          <button
            type="submit"
            disabled={saving || !dirty}
            className="rounded-xl bg-sage px-5 py-2.5 text-sm font-semibold text-white disabled:opacity-50"
          >
            {saving ? 'Saving…' : 'Save'}
          </button>
        </div>
      </div>
    </div>
  )
}

export function LeaveGuard({ open, onStay, onLeave }) {
  if (!open) return null
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-[var(--aal-ink)]/40 p-4 sm:items-center">
      <div className="w-full max-w-md rounded-2xl border border-[var(--aal-line)] bg-[var(--aal-card)] p-5">
        <h2 className="text-lg font-semibold">Leave without saving?</h2>
        <p className="mt-2 text-sm text-[var(--aal-muted)]">
          Changes to this profile will be lost if you leave now.
        </p>
        <div className="mt-5 flex justify-end gap-2">
          <button
            type="button"
            onClick={onStay}
            className="rounded-xl border border-[var(--aal-line)] px-4 py-2.5 text-sm font-semibold"
          >
            Stay
          </button>
          <button
            type="button"
            onClick={onLeave}
            className="rounded-xl bg-danger-muted px-4 py-2.5 text-sm font-semibold text-white"
          >
            Leave
          </button>
        </div>
      </div>
    </div>
  )
}

export function MeasureFields({ form, onChange }) {
  const imperial = form.units === 'imperial'
  const heightDisplay = imperial ? cmToInches(form.height_cm) : form.height_cm
  const weightDisplay = imperial ? kgToLb(form.weight) : form.weight

  return (
    <div className="grid gap-6 md:grid-cols-2">
      <label className="block">
        <span className="text-xs font-semibold uppercase tracking-wide text-[var(--aal-muted)]">
          Height ({imperial ? 'in' : 'cm'})
        </span>
        <input
          type="number"
          min={imperial ? 35 : 90}
          max={imperial ? 102 : 260}
          step={imperial ? 1 : 0.5}
          value={heightDisplay ?? ''}
          onChange={(event) =>
            onChange('height_cm', imperial ? inchesToCm(event.target.value) : event.target.value)
          }
          className={inputClass}
        />
        {imperial && form.height_cm ? (
          <p className="mt-2 text-xs text-[var(--aal-muted)]">{formatHeight(form.height_cm, 'imperial')}</p>
        ) : null}
      </label>
      <label className="block">
        <span className="text-xs font-semibold uppercase tracking-wide text-[var(--aal-muted)]">
          Weight ({imperial ? 'lb' : 'kg'})
        </span>
        <input
          type="number"
          min={imperial ? 55 : 25}
          max={imperial ? 770 : 350}
          step="0.1"
          value={weightDisplay ?? ''}
          onChange={(event) =>
            onChange('weight', imperial ? lbToKg(event.target.value) : event.target.value)
          }
          className={inputClass}
        />
      </label>
    </div>
  )
}

export function IdentityEditFields({ form, onChange, nameClass, children }) {
  return (
    <div className="space-y-6">
      <label className="block max-w-md">
        <span className="text-xs font-semibold uppercase tracking-wide text-[var(--aal-muted)]">
          Name
        </span>
        <input
          value={form.name || ''}
          onChange={(event) => onChange('name', event.target.value)}
          className={nameClass || inputClass}
          required
        />
      </label>
      {children}
    </div>
  )
}

export function TrainingView({ form }) {
  return (
    <FactorSections
      groups={[
        {
          key: 'goals',
          title: 'Goals',
          factors: [
            <FactorItem key="primary" label="Primary goal" wide>
              <TextBulletPoints text={form.primary_goal} />
            </FactorItem>,
            <FactorItem key="secondary" label="Secondary goal" wide>
              <TextBulletPoints text={form.secondary_goal} />
            </FactorItem>,
          ],
        },
        {
          key: 'event',
          title: 'Event & target',
          factors: [
            <FactorItem key="event" label="Event">
              <DisplayValue>
                {formatEventValue(form.goal_event_name, formatDate(form.goal_event_date))}
              </DisplayValue>
            </FactorItem>,
            <FactorItem key="target" label="Target">
              <DisplayValue>{form.goal_metric}</DisplayValue>
            </FactorItem>,
          ],
        },
        {
          key: 'fitness',
          title: 'Fitness & history',
          factors: [
            <FactorItem key="fitness" label="Fitness">
              <DisplayValue>{form.fitness_level}</DisplayValue>
            </FactorItem>,
            <FactorItem key="history" label="Training history">
              <DisplayValue>{historyLabel(form.training_history_months)}</DisplayValue>
            </FactorItem>,
          ],
        },
        {
          key: 'load',
          title: 'Current load',
          subtitle: 'What you are doing now — the coach calibrates from here.',
          factors: [
            <FactorItem key="volume" label="Weekly volume" wide>
              <WeeklyVolumePoints volume={form.current_weekly_volume} sports={form.sports} />
            </FactorItem>,
            <FactorItem key="longest" label="Longest recent session" wide>
              <DisplayValue>{form.longest_recent_session}</DisplayValue>
            </FactorItem>,
            <FactorItem key="prs" label="Recent results / PRs" wide>
              <DisplayValue>{form.race_prs}</DisplayValue>
            </FactorItem>,
          ],
        },
        {
          key: 'schedule',
          title: 'Weekly schedule',
          factors: [
            <FactorItem key="days" label="Days per week">
              <DisplayValue>
                {form.days_per_week != null ? String(form.days_per_week) : null}
              </DisplayValue>
            </FactorItem>,
            <FactorItem key="session" label="Session length">
              <DisplayValue>{durationLabel(form.workout_duration_minutes)}</DisplayValue>
            </FactorItem>,
            <FactorItem key="minutes" label="Weekly minutes">
              <DisplayValue>
                {form.weekly_minutes_budget != null ? `${form.weekly_minutes_budget} min` : null}
              </DisplayValue>
            </FactorItem>,
            <FactorItem key="time" label="Preferred time">
              <DisplayValue>{form.preferred_workout_time}</DisplayValue>
            </FactorItem>,
          ],
        },
      ]}
    />
  )
}

export function BodyView({ form }) {
  return (
    <FactorSections
      groups={[
        {
          key: 'body',
          factors: [
            <FactorItem key="sex" label="Sex">
              <DisplayValue>{sexLabel(form.sex)}</DisplayValue>
            </FactorItem>,
            <FactorItem key="dob" label="Date of birth">
              <DisplayValue>{formatDate(form.date_of_birth)}</DisplayValue>
            </FactorItem>,
            <FactorItem key="height" label="Height">
              <DisplayValue>{formatHeight(form.height_cm, form.units)}</DisplayValue>
            </FactorItem>,
            <FactorItem key="weight" label="Weight">
              <DisplayValue>{formatWeight(form.weight, form.units)}</DisplayValue>
            </FactorItem>,
            <FactorItem key="units" label="Units">
              <DisplayValue>{unitsLabel(form.units)}</DisplayValue>
            </FactorItem>,
          ],
        },
      ]}
    />
  )
}

export function HealthView({ form }) {
  const injuries = form.injuries || []
  return (
    <FactorSections
      groups={[
        {
          key: 'injuries',
          title: 'Injuries',
          factors: [
            <div key="list" className="sm:col-span-2">
              {injuries.length === 0 ? (
                <FactorItem label="Recorded injuries">
                  <span className="text-sm text-[var(--aal-muted)]">No injuries on file.</span>
                </FactorItem>
              ) : (
                <ul className="space-y-3">
                  {injuries.map((injury) => {
                    const summary = injurySummary(injury)
                    return (
                      <li
                        key={summary.title}
                        className="border-l-2 border-sage/45 pl-4"
                      >
                        <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-[var(--aal-muted)]">
                          {summary.title}
                        </p>
                        <p className="mt-1 font-semibold capitalize text-[var(--aal-ink)]">
                          {summary.detail || 'Noted'}
                        </p>
                        {summary.notes ? (
                          <p className="mt-1 text-sm leading-relaxed text-[var(--aal-muted)]">
                            {summary.notes}
                          </p>
                        ) : null}
                      </li>
                    )
                  })}
                </ul>
              )}
            </div>,
          ],
        },
        {
          key: 'limits',
          factors: [
            <FactorItem key="avoid" label="Anything else to avoid" wide>
              <DisplayValue>{form.injuries_limitations}</DisplayValue>
            </FactorItem>,
          ],
        },
      ]}
    />
  )
}

export function PreferencesView({ form }) {
  return (
    <FactorSections
      groups={[
        {
          key: 'prefs',
          factors: [
            <FactorItem key="equipment" label="Equipment" wide>
              <TextPills items={form.equipment} />
            </FactorItem>,
            <FactorItem key="love" label="Sessions you love" wide>
              <TextBulletPoints text={form.exercises_love} />
            </FactorItem>,
            <FactorItem key="hate" label="Sessions you hate" wide>
              <DisplayValue>{form.exercises_hate}</DisplayValue>
            </FactorItem>,
          ],
        },
      ]}
    />
  )
}

export function SettingsHint() {
  return (
    <p className="text-sm text-[var(--aal-muted)]">
      Privacy consents, blood type, and log out live in{' '}
      <Link to="/settings" className="font-medium text-sage underline decoration-dotted underline-offset-2">
        Settings
      </Link>
      .
    </p>
  )
}
