import { phaseLabel } from './seasonGuides'

export function buildWeekReviewMessage(context, constraints) {
  const season = context?.season
  const phase = season?.current_phase
  const intent = season?.week_intent
  const lines = [
    'Please review my training week before you build it.',
    '',
    'Season context:',
  ]

  if (season?.has_plan && phase) {
    lines.push(
      `- Phase: ${phaseLabel(phase.phase_type)} (week ${season.week_in_phase || '?'} of ${phase.week_count || '?'})`,
      `- Phase intent: ${phase.intent || intent?.focus || '—'}`,
      `- Volume bias: ${intent?.volume_bias ?? '—'} · Intensity: ${intent?.intensity_bias ?? '—'}`,
    )
    if (intent?.long_session_allowed_min) {
      lines.push(`- Long day up to: ${intent.long_session_allowed_min} min`)
    }
  } else if (season?.a_race) {
    lines.push(
      `- A-race: ${season.a_race.name} on ${season.a_race.date}`,
      '- No macro season plan yet — keep the week conservative.',
    )
  }

  const events = intent?.events || []
  if (events.length) {
    lines.push('', 'Events this week:')
    events.forEach((event) => {
      lines.push(`- ${event.priority}-race ${event.name} on ${event.date}`)
    })
  }

  const notes = (constraints || context?.planning_notes || '').trim()
  if (notes) {
    lines.push('', 'My schedule and preferences:', notes)
  } else {
    lines.push('', 'My schedule and preferences: (not specified — ask what days and times work)')
  }

  lines.push(
    '',
    'Review only — do not build the week table yet. Tell me conflicts, phase fit, and what I should consider.',
  )
  return lines.join('\n')
}

export function buildWeekCommitMessage(context, constraints) {
  const notes = (constraints || context?.planning_notes || '').trim()
  const lines = [
    'Plan my week now using your review above and my constraints.',
    'Build the full week table and structured workouts for the remaining days this week.',
  ]
  if (notes) {
    lines.push('', 'Constraints to honour:', notes)
  }
  return lines.join('\n')
}

export function buildRecoveryShiftMessage(phase, extraNotes = '') {
  const range =
    phase?.start_date && phase?.end_date
      ? `${phase.start_date} → ${phase.end_date}`
      : 'this recovery block'
  const lines = [
    `I need to adjust when my recovery week runs (${range}).`,
    'Review whether I should shorten/lengthen this block or replan remaining phases.',
    extraNotes.trim(),
  ].filter(Boolean)
  return lines.join('\n\n')
}
