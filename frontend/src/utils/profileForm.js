import { toDateInput, toNumberOrNull, toTextOrNull } from './profileView'

export const GOAL_FIELDS = [
  { key: 'primary_goal', label: 'Primary goal', type: 'textarea' },
  { key: 'secondary_goal', label: 'Secondary goal', type: 'textarea' },
  { key: 'goal_event_name', label: 'Goal event', type: 'text' },
  { key: 'goal_event_date', label: 'Event date', type: 'date' },
  { key: 'goal_metric', label: 'Target result', type: 'text' },
]

export const FITNESS_FIELDS = [
  {
    key: 'fitness_level',
    label: 'Fitness level',
    type: 'chips-single',
    options: ['Complete beginner', 'Beginner', 'Intermediate', 'Advanced'],
  },
  {
    key: 'training_history_months',
    label: 'How long have you been training consistently?',
    type: 'chips-single',
    options: [
      { value: 0, label: 'Just starting' },
      { value: 3, label: '~3 months' },
      { value: 6, label: '~6 months' },
      { value: 12, label: '1 year' },
      { value: 36, label: '3+ years' },
      { value: 60, label: '5+ years' },
    ],
  },
  { key: 'current_weekly_volume', type: 'weekly-volume' },
  { key: 'longest_recent_session', label: 'Longest recent session', type: 'text' },
  { key: 'race_prs', label: 'Recent results / PRs', type: 'textarea' },
]

export const TIME_FIELDS = [
  {
    key: 'days_per_week',
    label: 'Training days per week',
    type: 'chips-single',
    options: [1, 2, 3, 4, 5, 6, 7],
  },
  {
    key: 'workout_duration_minutes',
    label: 'Typical session length',
    help: 'Usual weekday length. Long rides and key sessions can be much longer.',
    type: 'chips-single',
    options: [
      { value: 20, label: '20 min' },
      { value: 30, label: '30 min' },
      { value: 45, label: '45 min' },
      { value: 60, label: '60 min' },
      { value: 90, label: '90 min' },
      { value: 120, label: '2 hr' },
    ],
  },
  {
    key: 'weekly_minutes_budget',
    label: 'Weekly minutes budget',
    type: 'number',
    min: 0,
    max: 3000,
    help: 'A soft weekly target, not days × typical session. Leave blank if unsure.',
  },
  {
    key: 'preferred_workout_time',
    label: 'Preferred time of day',
    type: 'chips-single',
    options: ['Morning', 'Lunch', 'Evening', 'Flexible'],
  },
]

export const BODY_FIELDS = [
  {
    key: 'sex',
    label: 'Sex',
    type: 'chips-single',
    options: [
      { value: 'female', label: 'Female' },
      { value: 'male', label: 'Male' },
      { value: 'other', label: 'Other' },
      { value: 'prefer_not', label: 'Prefer not to say' },
    ],
  },
  { key: 'date_of_birth', label: 'Date of birth', type: 'date' },
  {
    key: 'units',
    label: 'Preferred units',
    type: 'chips-single',
    options: [
      { value: 'metric', label: 'Metric (km, kg)' },
      { value: 'imperial', label: 'Imperial (mi, lb)' },
    ],
  },
]

export const PREFERENCE_FIELDS = [
  {
    key: 'equipment',
    label: 'Equipment access',
    type: 'chips-multi',
    options: [
      'Full gym',
      'Home dumbbells',
      'Barbell + rack',
      'Bodyweight only',
      'Resistance bands',
      'Kettlebells',
      'Pull-up bar',
      'Cardio machines',
      'Road bike',
      'Indoor trainer',
      'Pool access',
    ],
  },
  { key: 'exercises_love', label: 'Sessions you love', type: 'textarea' },
  { key: 'exercises_hate', label: 'Sessions you hate', type: 'textarea' },
]

export function buildProfileForm(profile) {
  if (!profile) return null
  return {
    ...profile,
    threshold_pace: profile.threshold_pace_display || profile.threshold_pace || '',
    lt1_pace: profile.lt1_pace_display || profile.lt1_pace || '',
    marathon_pace: profile.marathon_pace_display || profile.marathon_pace || '',
    css_pace: profile.css_pace_display || profile.css_pace || '',
    zone_run_hr_method: profile.zone_run_hr_method || 'lthr',
    date_of_birth: toDateInput(profile.date_of_birth),
    goal_event_date: toDateInput(profile.goal_event_date),
    sports: profile.sports || [],
    injuries: profile.injuries || [],
    current_weekly_volume:
      profile.current_weekly_volume && !Array.isArray(profile.current_weekly_volume)
        ? profile.current_weekly_volume
        : {},
    consents: profile.consents || { ai_coaching: false, health_data: false, research: false },
  }
}

export function buildProfileSavePayload(form) {
  return {
    name: form.name,
    primary_goal: toTextOrNull(form.primary_goal),
    secondary_goal: toTextOrNull(form.secondary_goal),
    equipment: toTextOrNull(form.equipment),
    days_per_week: toNumberOrNull(form.days_per_week),
    workout_duration_minutes: toNumberOrNull(form.workout_duration_minutes),
    preferred_workout_time: toTextOrNull(form.preferred_workout_time),
    injuries_limitations: toTextOrNull(form.injuries_limitations),
    fitness_level: toTextOrNull(form.fitness_level),
    exercises_hate: toTextOrNull(form.exercises_hate),
    exercises_love: toTextOrNull(form.exercises_love),
    sex: toTextOrNull(form.sex),
    date_of_birth: toTextOrNull(form.date_of_birth),
    height_cm: toNumberOrNull(form.height_cm),
    weight: toNumberOrNull(form.weight) ?? undefined,
    units: form.units === 'imperial' ? 'imperial' : 'metric',
    training_history_months: toNumberOrNull(form.training_history_months),
    current_weekly_volume: form.current_weekly_volume || {},
    longest_recent_session: toTextOrNull(form.longest_recent_session),
    race_prs: toTextOrNull(form.race_prs),
    weekly_minutes_budget: toNumberOrNull(form.weekly_minutes_budget),
    goal_event_name: toTextOrNull(form.goal_event_name),
    goal_event_date: toTextOrNull(form.goal_event_date),
    goal_metric: toTextOrNull(form.goal_metric),
    planning_notes: toTextOrNull(form.planning_notes),
    ftp_watts: toNumberOrNull(form.ftp_watts),
    lthr_bpm: toNumberOrNull(form.lthr_bpm),
    bike_lthr_bpm: toNumberOrNull(form.bike_lthr_bpm),
    max_hr_bpm: toNumberOrNull(form.max_hr_bpm),
    resting_hr_bpm: toNumberOrNull(form.resting_hr_bpm),
    threshold_pace: toTextOrNull(form.threshold_pace),
    lt1_pace: toTextOrNull(form.lt1_pace),
    marathon_pace: toTextOrNull(form.marathon_pace),
    css_pace: toTextOrNull(form.css_pace),
    vo2max: toNumberOrNull(form.vo2max),
    zone_run_hr_method: toTextOrNull(form.zone_run_hr_method) || 'lthr',
    sports: form.sports || [],
    injuries: form.injuries || [],
    cycle_tracking_enabled: Boolean(form.cycle_tracking_enabled),
    cycle_length_manual: toNumberOrNull(form.cycle_length_manual),
  }
}
