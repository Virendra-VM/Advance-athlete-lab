import { VOLUME_UNIT_BY_SPORT } from './onboardingSteps'

export const PROFILE_SECTIONS = [
  { id: 'identity', label: 'Identity' },
  { id: 'training', label: 'Training' },
  { id: 'body', label: 'Body' },
  { id: 'health', label: 'Health' },
  { id: 'preferences', label: 'Preferences' },
]

export const COMPLETENESS_ITEMS = [
  { key: 'name', label: 'Name', section: 'identity' },
  { key: 'sports', label: 'Sports', section: 'identity', kind: 'sports' },
  { key: 'sex', label: 'Sex', section: 'body' },
  { key: 'date_of_birth', label: 'Date of birth', section: 'body' },
  { key: 'height_cm', label: 'Height', section: 'body' },
  { key: 'weight', label: 'Weight', section: 'body' },
  { key: 'primary_goal', label: 'Primary goal', section: 'training' },
  { key: 'fitness_level', label: 'Fitness level', section: 'training' },
  { key: 'days_per_week', label: 'Training days', section: 'training' },
  { key: 'workout_duration_minutes', label: 'Session length', section: 'training' },
  { key: 'preferred_workout_time', label: 'Preferred time of day', section: 'training' },
  { key: 'equipment', label: 'Equipment', section: 'preferences' },
  { key: 'training_history_months', label: 'Training history', section: 'training' },
]

const SEX_LABELS = {
  female: 'Female',
  male: 'Male',
  other: 'Other',
  prefer_not: 'Prefer not to say',
}

const HISTORY_LABELS = {
  0: 'Just starting',
  3: '~3 months',
  6: '~6 months',
  12: '1 year',
  36: '3+ years',
  60: '5+ years',
}

const DURATION_LABELS = {
  20: '20 min',
  30: '30 min',
  45: '45 min',
  60: '60 min',
  90: '90 min',
  120: '2 hr',
}

const INJURY_STATUS_LABELS = {
  active: 'Ongoing',
  past: 'Past',
}

export function isEmptyValue(value) {
  if (value == null) return true
  if (Array.isArray(value)) return value.length === 0
  if (typeof value === 'object') return Object.keys(value).length === 0
  return String(value).trim() === ''
}

export function toNumberOrNull(value) {
  if (value == null || String(value).trim() === '') return null
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : null
}

export function toTextOrNull(value) {
  const text = (value ?? '').toString().trim()
  return text || null
}

export function toDateInput(value) {
  if (!value) return ''
  if (typeof value === 'string') return value.slice(0, 10)
  if (value instanceof Date && !Number.isNaN(value.getTime())) {
    const month = String(value.getMonth() + 1).padStart(2, '0')
    const day = String(value.getDate()).padStart(2, '0')
    return `${value.getFullYear()}-${month}-${day}`
  }
  return String(value).slice(0, 10)
}

export function parseIsoDate(value) {
  if (!value) return null
  if (typeof value === 'string' && /^\d{4}-\d{2}-\d{2}/.test(value)) {
    const [year, month, day] = value.slice(0, 10).split('-').map(Number)
    return new Date(year, month - 1, day)
  }
  const date = value instanceof Date ? value : new Date(value)
  return Number.isNaN(date.getTime()) ? null : date
}

export function formatDate(value) {
  const date = parseIsoDate(value)
  if (!date) return null
  return date.toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' })
}

export function ageFromDob(dob) {
  const date = parseIsoDate(dob)
  if (!date) return null
  const today = new Date()
  let years = today.getFullYear() - date.getFullYear()
  const beforeBirthday =
    today.getMonth() < date.getMonth() ||
    (today.getMonth() === date.getMonth() && today.getDate() < date.getDate())
  if (beforeBirthday) years -= 1
  return years >= 5 && years <= 120 ? years : null
}

export function displayAge(form) {
  return ageFromDob(form.date_of_birth) ?? toNumberOrNull(form.age)
}

export function cmToInches(cm) {
  const value = toNumberOrNull(cm)
  if (value == null) return null
  return Math.round(value / 2.54)
}

export function inchesToCm(inches) {
  const value = toNumberOrNull(inches)
  if (value == null) return null
  return Math.round(value * 2.54 * 10) / 10
}

export function kgToLb(kg) {
  const value = toNumberOrNull(kg)
  if (value == null) return null
  return Math.round(value * 2.20462 * 10) / 10
}

export function lbToKg(lb) {
  const value = toNumberOrNull(lb)
  if (value == null) return null
  return Math.round((value / 2.20462) * 10) / 10
}

export function formatHeight(cm, units) {
  const value = toNumberOrNull(cm)
  if (value == null) return null
  if (units === 'imperial') {
    const totalIn = value / 2.54
    const feet = Math.floor(totalIn / 12)
    const inches = Math.round(totalIn % 12)
    return `${feet}'${inches}"`
  }
  return `${Math.round(value)} cm`
}

export function formatWeight(kg, units) {
  const value = toNumberOrNull(kg)
  if (value == null) return null
  if (units === 'imperial') return `${kgToLb(value)} lb`
  return `${value} kg`
}

export function sexLabel(value) {
  if (!value) return null
  return SEX_LABELS[value] || value
}

export function unitsLabel(value) {
  return value === 'imperial' ? 'Imperial (mi, lb)' : 'Metric (km, kg)'
}

export function historyLabel(months) {
  const value = toNumberOrNull(months)
  if (value == null) return null
  if (HISTORY_LABELS[value]) return HISTORY_LABELS[value]
  if (value === 1) return '1 month'
  return `${value} months`
}

export function durationLabel(minutes) {
  const value = toNumberOrNull(minutes)
  if (value == null) return null
  return DURATION_LABELS[value] || `${value} min`
}

export function splitList(value) {
  if (Array.isArray(value)) return value.map((part) => String(part).trim()).filter(Boolean)
  return String(value || '')
    .split(',')
    .map((part) => part.trim())
    .filter(Boolean)
}

export function goalHeadline(form) {
  const parts = [toTextOrNull(form.primary_goal), toTextOrNull(form.goal_metric)].filter(Boolean)
  return parts.join(' · ') || null
}

export function goalSubline(form) {
  const bits = []
  if (form.goal_event_name) bits.push(form.goal_event_name)
  const eventDate = formatDate(form.goal_event_date)
  if (eventDate) bits.push(eventDate)
  return bits.join(' · ') || null
}

export function weekSummary(form) {
  const days = toNumberOrNull(form.days_per_week)
  const duration = durationLabel(form.workout_duration_minutes)
  const time = toTextOrNull(form.preferred_workout_time)
  const parts = []
  if (days != null) parts.push(`${days} day${days === 1 ? '' : 's'}`)
  if (duration) parts.push(duration)
  if (time) parts.push(time.toLowerCase())
  return parts.length ? parts.join(' · ') : null
}

export function volumeSummary(volume, sports) {
  const entries = Object.entries(volume || {}).filter(([, value]) => !isEmptyValue(value))
  if (!entries.length) return []
  const sportSet = new Set((sports || []).map((entry) => entry.sport))
  return entries.map(([sport, value]) => {
    const unit = VOLUME_UNIT_BY_SPORT[sport] || 'per week'
    const prefix = sportSet.size && !sportSet.has(sport) ? sport : sport
    return `${prefix} ${value} ${unit}`
  })
}

export function injurySummary(injury) {
  const status = INJURY_STATUS_LABELS[injury.status] || injury.status || 'Noted'
  const severity = injury.severity ? String(injury.severity) : null
  const detail = [status, severity].filter(Boolean).join(', ')
  const notes = toTextOrNull(injury.notes)
  return {
    title: injury.body_region || injury.condition || 'Injury',
    detail,
    notes,
  }
}

export function missingCompletenessItems(form) {
  return COMPLETENESS_ITEMS.filter((item) => {
    if (item.kind === 'sports') return !(form.sports || []).length
    return isEmptyValue(form[item.key])
  })
}

export function scrollToProfileSection(sectionId) {
  const node = document.getElementById(`profile-${sectionId}`)
  node?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

export function sectionFromHash(hash) {
  const id = (hash || '').replace(/^#/, '')
  if (!id) return null
  if (id.startsWith('profile-')) return id.replace('profile-', '')
  return PROFILE_SECTIONS.some((section) => section.id === id) ? id : null
}

function sortedVolume(volume) {
  return Object.fromEntries(
    Object.entries(volume || {})
      .filter(([, value]) => !isEmptyValue(value))
      .sort(([left], [right]) => left.localeCompare(right)),
  )
}

export function normalizeProfileForm(form) {
  if (!form) return null
  return {
    name: toTextOrNull(form.name),
    sex: toTextOrNull(form.sex),
    date_of_birth: toDateInput(form.date_of_birth) || null,
    height_cm: toNumberOrNull(form.height_cm),
    weight: toNumberOrNull(form.weight),
    units: form.units === 'imperial' ? 'imperial' : 'metric',
    sports: (form.sports || []).map((entry) => ({
      sport: entry.sport,
      priority: entry.priority || 'primary',
      experience_level: entry.experience_level || null,
    })),
    primary_goal: toTextOrNull(form.primary_goal),
    secondary_goal: toTextOrNull(form.secondary_goal),
    goal_event_name: toTextOrNull(form.goal_event_name),
    goal_event_date: toDateInput(form.goal_event_date) || null,
    goal_metric: toTextOrNull(form.goal_metric),
    fitness_level: toTextOrNull(form.fitness_level),
    training_history_months: toNumberOrNull(form.training_history_months),
    current_weekly_volume: sortedVolume(form.current_weekly_volume),
    longest_recent_session: toTextOrNull(form.longest_recent_session),
    race_prs: toTextOrNull(form.race_prs),
    days_per_week: toNumberOrNull(form.days_per_week),
    workout_duration_minutes: toNumberOrNull(form.workout_duration_minutes),
    weekly_minutes_budget: toNumberOrNull(form.weekly_minutes_budget),
    ftp_watts: toNumberOrNull(form.ftp_watts),
    lthr_bpm: toNumberOrNull(form.lthr_bpm),
    max_hr_bpm: toNumberOrNull(form.max_hr_bpm),
    preferred_workout_time: toTextOrNull(form.preferred_workout_time),
    injuries: (form.injuries || []).map((entry) => ({
      body_region: entry.body_region,
      status: entry.status || 'past',
      severity: entry.severity || 'mild',
      notes: toTextOrNull(entry.notes),
    })),
    injuries_limitations: toTextOrNull(form.injuries_limitations),
    equipment: toTextOrNull(form.equipment),
    exercises_love: toTextOrNull(form.exercises_love),
    exercises_hate: toTextOrNull(form.exercises_hate),
  }
}

export function formsEqual(left, right) {
  return JSON.stringify(normalizeProfileForm(left)) === JSON.stringify(normalizeProfileForm(right))
}
