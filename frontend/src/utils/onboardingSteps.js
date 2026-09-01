/**
 * Onboarding intake: short themed screens (one job per screen) rather than
 * one question at a time. Each screen declares fields the wizard renders.
 */

export const SPORT_OPTIONS = [
  'Running',
  'Cycling',
  'Swimming',
  'Strength training',
  'Trail running',
  'Triathlon',
  'Walking / Hiking',
  'Rowing',
  'Yoga / Mobility',
  'Team sport',
]

export const EXPERIENCE_LEVELS = ['New to it', 'Beginner', 'Intermediate', 'Advanced']

export const BODY_REGIONS = [
  'Knee',
  'Lower back',
  'Ankle / Foot',
  'Hip',
  'Shoulder',
  'Achilles',
  'Hamstring',
  'Calf',
  'Wrist / Elbow',
  'Neck',
]

export const INJURY_STATUS_OPTIONS = [
  { value: 'active', label: 'Ongoing' },
  { value: 'past', label: 'Past' },
]

export const INJURY_SEVERITY_OPTIONS = ['mild', 'moderate', 'severe']

export const BLOOD_TYPES = ['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-']

export const VOLUME_UNIT_BY_SPORT = {
  Running: 'km / week',
  'Trail running': 'km / week',
  Cycling: 'km / week',
  Swimming: 'm / week',
  Rowing: 'km / week',
  'Walking / Hiking': 'km / week',
  Triathlon: 'hours / week',
  'Strength training': 'sessions / week',
  'Yoga / Mobility': 'sessions / week',
  'Team sport': 'sessions / week',
}

export const ONBOARDING_STEPS = [
  {
    id: 'welcome',
    eyebrow: 'Welcome',
    title: "Let's build your coach",
    subtitle:
      'A few short screens so your plans match your body, your sports, and your real week. Everything here is editable later.',
    type: 'intro',
    bullets: [
      'Body basics keep intensity and pacing realistic',
      'Sports and time budget shape your weekly structure',
      'Injuries let us filter out anything risky',
    ],
    fields: [],
  },
  {
    id: 'body',
    eyebrow: 'About you',
    title: 'Your basics',
    subtitle: 'These calibrate load, pacing, and intensity targets.',
    fields: [
      { key: 'name', label: 'Name', type: 'text', placeholder: 'Your name' },
      {
        key: 'sex',
        label: 'Sex',
        type: 'chips-single',
        required: true,
        options: [
          { value: 'female', label: 'Female' },
          { value: 'male', label: 'Male' },
          { value: 'other', label: 'Other' },
          { value: 'prefer_not', label: 'Prefer not to say' },
        ],
        help: 'Used for physiology-aware defaults only.',
      },
      { key: 'date_of_birth', label: 'Date of birth', type: 'date', required: true },
      {
        key: 'height_cm',
        label: 'Height',
        type: 'number',
        suffix: 'cm',
        min: 90,
        max: 260,
        required: true,
      },
      {
        key: 'weight',
        label: 'Weight',
        type: 'number',
        suffix: 'kg',
        step: '0.1',
        min: 25,
        max: 350,
        required: true,
      },
      {
        key: 'units',
        label: 'Preferred units',
        type: 'chips-single',
        options: [
          { value: 'metric', label: 'Metric (km, kg)' },
          { value: 'imperial', label: 'Imperial (mi, lb)' },
        ],
      },
    ],
  },
  {
    id: 'sports',
    eyebrow: 'Your sports',
    title: 'What do you train?',
    subtitle: 'Pick your main sports first, then set your experience in each.',
    fields: [{ key: 'sports', type: 'sports', required: true }],
  },
  {
    id: 'goal',
    eyebrow: 'Your goal',
    title: "What are you working toward?",
    subtitle: 'One clear goal beats five vague ones.',
    fields: [
      {
        key: 'primary_goal',
        label: 'Primary goal',
        type: 'chips-text',
        required: true,
        options: [
          'Run a 5K',
          'Half marathon',
          'Marathon',
          'Build muscle',
          'Lose weight',
          'Get more active',
          'Improve endurance',
          'Reduce stress',
        ],
      },
      {
        key: 'secondary_goal',
        label: 'Secondary goal',
        type: 'chips-text',
        options: ['Get stronger', 'Improve mobility', 'More energy', 'Better sleep'],
      },
      { key: 'goal_event_name', label: 'Goal event (optional)', type: 'text', placeholder: 'e.g. City Half Marathon' },
      { key: 'goal_event_date', label: 'Event date (optional)', type: 'date' },
      {
        key: 'goal_metric',
        label: 'Target result (optional)',
        type: 'text',
        placeholder: 'e.g. sub 1:45, finish strong, 10 kg lift PR',
      },
    ],
  },
  {
    id: 'fitness',
    eyebrow: 'Current fitness',
    title: 'Where are you starting from?',
    subtitle: 'No judgment — this sets your first week, not your ceiling.',
    fields: [
      {
        key: 'fitness_level',
        label: 'Fitness level',
        type: 'chips-single',
        required: true,
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
      {
        key: 'longest_recent_session',
        label: 'Longest recent session',
        type: 'text',
        placeholder: 'e.g. 12 km run, 60 km ride, 45 min gym',
      },
      {
        key: 'race_prs',
        label: 'Recent results or PRs (optional)',
        type: 'textarea',
        placeholder: 'e.g. 5K in 24:10 last month, 100 kg squat',
        help: 'Helps set pace and intensity targets from day one.',
      },
    ],
  },
  {
    id: 'time',
    eyebrow: 'Your week',
    title: 'How much time do you really have?',
    subtitle: 'Be honest — 3 consistent days beats 6 you skip.',
    fields: [
      {
        key: 'days_per_week',
        label: 'Training days per week',
        type: 'chips-single',
        required: true,
        options: [1, 2, 3, 4, 5, 6, 7],
      },
      {
        key: 'workout_duration_minutes',
        label: 'Typical session length',
        type: 'chips-single',
        required: true,
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
        label: 'Total weekly minutes you can commit',
        type: 'number',
        suffix: 'min',
        min: 0,
        max: 3000,
        help: 'Leave blank and we will estimate from days x session length.',
      },
      {
        key: 'preferred_workout_time',
        label: 'Preferred time of day',
        type: 'chips-single',
        required: true,
        options: ['Morning', 'Lunch', 'Evening', 'Flexible'],
      },
    ],
  },
  {
    id: 'injuries',
    eyebrow: 'Safety first',
    title: 'Anything we should train around?',
    subtitle:
      'Add ongoing or past issues so we can filter risky sessions. Skip if nothing applies.',
    fields: [
      { key: 'injuries', type: 'injuries' },
      {
        key: 'injuries_limitations',
        label: 'Anything else to avoid',
        type: 'textarea',
        placeholder: 'e.g. no jumping, avoid overhead pressing',
      },
    ],
  },
  {
    id: 'equipment',
    eyebrow: 'Setup',
    title: 'What can you train with?',
    subtitle: 'We only prescribe what you can actually do.',
    fields: [
      {
        key: 'equipment',
        label: 'Equipment access',
        type: 'chips-multi',
        required: true,
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
      {
        key: 'exercises_love',
        label: 'Sessions you love',
        type: 'chips-text',
        options: ['Long runs', 'Intervals', 'Hills', 'Cycling', 'Swimming', 'Heavy lifting', 'Yoga'],
      },
      {
        key: 'exercises_hate',
        label: 'Sessions you hate',
        type: 'chips-text',
        options: ['Burpees', 'Treadmill', 'HIIT', 'Long runs', 'Track work', 'Cardio machines'],
      },
    ],
  },
  {
    id: 'optional',
    eyebrow: 'Optional',
    title: 'Anything else? All optional',
    subtitle: 'Skip this entirely — nothing here is required to finish.',
    optional: true,
    fields: [
      {
        key: 'blood_type',
        label: 'Blood type',
        type: 'chips-single',
        options: BLOOD_TYPES,
        help: 'Stored for emergencies and left out of coaching prompts.',
      },
    ],
  },
  {
    id: 'review',
    eyebrow: 'Almost done',
    title: 'Review and consent',
    subtitle: 'Confirm what your coach may use. You can change these anytime.',
    type: 'review',
    fields: [{ key: 'consents', type: 'consents', required: true }],
  },
]

export function primarySports(answers) {
  return (answers.sports || []).filter((entry) => entry.priority !== 'secondary')
}

function isEmptyValue(value) {
  if (value == null) return true
  if (Array.isArray(value)) return value.length === 0
  if (typeof value === 'object') return Object.keys(value).length === 0
  return String(value).trim() === ''
}

export function isFieldComplete(field, answers) {
  const value = answers[field.key]
  if (field.type === 'sports') return primarySports(answers).length > 0
  if (field.type === 'consents') return Boolean(value?.ai_coaching)
  return !isEmptyValue(value)
}

export function isStepComplete(step, answers) {
  return (step.fields || [])
    .filter((field) => field.required)
    .every((field) => isFieldComplete(field, answers))
}

export function defaultAnswers(profile) {
  return {
    name: profile?.name || '',
    units: profile?.units || 'metric',
    sports: [],
    injuries: [],
    current_weekly_volume: {},
    consents: { ai_coaching: false, health_data: false, research: false },
  }
}

function cleanText(value) {
  const text = (value ?? '').toString().trim()
  return text || null
}

function toNumber(value) {
  if (value == null || String(value).trim() === '') return null
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : null
}

export function buildOnboardingPayload(answers) {
  const sports = (answers.sports || [])
    .filter((entry) => entry.sport)
    .map((entry) => ({
      sport: entry.sport,
      priority: entry.priority === 'secondary' ? 'secondary' : 'primary',
      experience_level: cleanText(entry.experience_level),
      weekly_preference_days: toNumber(entry.weekly_preference_days),
    }))

  const injuries = (answers.injuries || [])
    .filter((entry) => entry.body_region)
    .map((entry) => ({
      body_region: entry.body_region,
      condition: cleanText(entry.condition),
      status: entry.status === 'active' ? 'active' : 'past',
      severity: cleanText(entry.severity),
      notes: cleanText(entry.notes),
    }))

  const volumeEntries = Object.entries(answers.current_weekly_volume || {}).filter(
    ([, value]) => String(value ?? '').trim() !== '',
  )

  const days = toNumber(answers.days_per_week) ?? 3
  const duration = toNumber(answers.workout_duration_minutes) ?? 45

  return {
    // v1 required answers
    primary_goal: cleanText(answers.primary_goal) || 'General fitness',
    secondary_goal: cleanText(answers.secondary_goal),
    equipment: cleanText(answers.equipment) || 'Bodyweight only',
    days_per_week: days,
    workout_duration_minutes: duration,
    preferred_workout_time: cleanText(answers.preferred_workout_time) || 'Flexible',
    injuries_limitations: cleanText(answers.injuries_limitations),
    fitness_level: cleanText(answers.fitness_level) || 'Beginner',
    exercises_hate: cleanText(answers.exercises_hate),
    exercises_love: cleanText(answers.exercises_love),

    // v2 intake
    name: cleanText(answers.name),
    sex: cleanText(answers.sex),
    date_of_birth: cleanText(answers.date_of_birth),
    height_cm: toNumber(answers.height_cm),
    weight: toNumber(answers.weight),
    blood_type: cleanText(answers.blood_type),
    units: answers.units === 'imperial' ? 'imperial' : 'metric',
    training_history_months: toNumber(answers.training_history_months),
    current_weekly_volume: volumeEntries.length ? Object.fromEntries(volumeEntries) : null,
    longest_recent_session: cleanText(answers.longest_recent_session),
    race_prs: cleanText(answers.race_prs),
    weekly_minutes_budget: toNumber(answers.weekly_minutes_budget) ?? days * duration,
    goal_event_name: cleanText(answers.goal_event_name),
    goal_event_date: cleanText(answers.goal_event_date),
    goal_metric: cleanText(answers.goal_metric),
    sports,
    injuries,
    consents: {
      ai_coaching: Boolean(answers.consents?.ai_coaching),
      health_data: Boolean(answers.consents?.health_data),
      research: Boolean(answers.consents?.research),
    },
  }
}

export function buildConfirmationMessage(answers) {
  const sports = primarySports(answers)
    .map((entry) => entry.sport)
    .join(', ')
  const days = answers.days_per_week || '?'
  const duration = answers.workout_duration_minutes || '?'
  const goal = answers.primary_goal || 'your goal'
  const limitations = (answers.injuries || []).length
    ? `${answers.injuries.length} injury note${answers.injuries.length > 1 ? 's' : ''} on file`
    : 'no injuries on file'
  return `${sports || 'Training'} toward ${goal}, ${days} days a week at about ${duration} minutes a session, with ${limitations}.`
}
