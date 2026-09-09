/**
 * Athlete-facing copy for the Season Plan page.
 *
 * The season skeleton is drawn by the Python periodization engine (retrograde
 * from the A-race). This file only explains what each block is for and which
 * button — Replan or Rebuild — the athlete should reach for.
 */

export const PHASE_ORDER = ['base', 'build', 'peak', 'taper', 'restore', 'recovery_week']

export const PHASE_GUIDES = {
  base: {
    label: 'Base',
    tagline: 'Build the engine',
    why: 'The longest block, because aerobic fitness and tissue durability take the most weeks to build and they hold up the rest of the season.',
    focus: [
      'Easy aerobic volume — most weeks are steady, conversational work',
      'Strength and mobility while the running is still gentle',
      'Frequency over heroics: showing up often beats one big day',
    ],
    avoid: [
      'Race-pace efforts this far out — they cost more than they add',
      'Jumping weekly volume more than about 10 percent',
    ],
    science:
      'Aerobic adaptations (mitochondria, capillaries, tendon stiffness) respond to accumulated easy volume over months, not to hard sessions over weeks.',
  },
  build: {
    label: 'Build',
    tagline: 'Raise the ceiling',
    why: 'With a base under you, this block lifts your threshold — the pace you can hold before lactate runs away from you.',
    focus: [
      'Tempo, threshold, and over-under work once or twice a week',
      'Keep the long day — volume holds while quality goes up',
      'Easy days genuinely easy so the hard days land',
    ],
    avoid: [
      'Turning every session hard — two quality days a week is plenty',
      'Dropping the long session to make room for intervals',
    ],
    science:
      'Threshold and LT2/FTP improve fastest with repeated controlled work at or just under threshold, layered on an existing aerobic base.',
  },
  peak: {
    label: 'Peak',
    tagline: 'Sharpen for race day',
    why: 'Fitness is largely set by now. This block teaches your body the exact pace, terrain, and fuelling of the A-race.',
    focus: [
      'Race-pace sessions and pacing rehearsals',
      'Practice race-day fuelling, kit, and start-line routine',
      'Muscular endurance — holding form when tired',
    ],
    avoid: [
      'Chasing new fitness with extra volume — too late to help, early enough to hurt',
      'Testing anything new on race week',
    ],
    science:
      'Specificity peaks close to competition: race-pace economy and pacing accuracy improve with rehearsal, not with more aerobic load.',
  },
  taper: {
    label: 'Taper',
    tagline: 'Bank the freshness',
    why: 'Volume drops sharply so accumulated fatigue clears while fitness stays. This is where the work of the whole season gets cashed in.',
    focus: [
      'Cut volume roughly 40 to 60 percent, keep some race-pace touches',
      'Protect sleep — this is the highest-value recovery week of the season',
      'Short, sharp, and confident sessions only',
    ],
    avoid: [
      'Panic sessions to "check" fitness — they only add fatigue',
      'Going completely flat: keep frequency and a little intensity',
    ],
    science:
      'A 40 to 60 percent volume reduction with maintained intensity over one to two weeks reliably improves performance; fitness decays far slower than fatigue.',
  },
  restore: {
    label: 'Restore',
    tagline: 'Reset after the race',
    why: 'A week for the nervous system and connective tissue to come back down. Skipping it is how good seasons turn into injured ones.',
    focus: [
      'Easy aerobic movement, mobility, and walking',
      'Sleep and food first — training second',
      'Reflect on the race before planning the next one',
    ],
    avoid: [
      'Jumping into the next block while still sore',
      'Booking a new A-race in the first few days on adrenaline',
    ],
    science:
      'Post-competition parasympathetic recovery and tissue repair take days to weeks; early hard loading raises injury and illness risk.',
  },
  recovery_week: {
    label: 'Recovery week',
    tagline: 'Absorb the work',
    why: 'Planned every fourth week or so. Training does not make you fitter — recovering from training does. This is where the gains land.',
    focus: [
      'Keep session frequency, cut duration and intensity about 30 percent',
      'Same schedule, smaller doses',
      'Watch sleep and resting HR come back toward usual',
    ],
    avoid: [
      'Treating it as an optional week to skip',
      'Sneaking in "just one" hard session',
    ],
    science:
      'Adaptation happens during the recovery from overload. Scheduled down weeks prevent the slow accumulation that becomes overreaching.',
  },
}

export const PHASE_ACCENTS = {
  base: {
    bar: 'bg-indigo-700',
    dot: 'bg-indigo-700',
    chip: 'bg-indigo-500/15 text-indigo-700 dark:text-indigo-300',
    ring: 'border-indigo-500/30',
  },
  build: {
    bar: 'bg-blue-500',
    dot: 'bg-blue-500',
    chip: 'bg-blue-500/15 text-blue-700 dark:text-blue-300',
    ring: 'border-blue-500/30',
  },
  peak: {
    bar: 'bg-sky-500',
    dot: 'bg-sky-500',
    chip: 'bg-sky-500/15 text-sky-700 dark:text-sky-300',
    ring: 'border-sky-500/30',
  },
  taper: {
    bar: 'bg-amber-500',
    dot: 'bg-amber-500',
    chip: 'bg-amber-500/15 text-amber-700 dark:text-amber-300',
    ring: 'border-amber-500/30',
  },
  restore: {
    bar: 'bg-emerald-500',
    dot: 'bg-emerald-500',
    chip: 'bg-emerald-500/15 text-emerald-700 dark:text-emerald-300',
    ring: 'border-emerald-500/30',
  },
  recovery_week: {
    bar: 'bg-slate-400',
    dot: 'bg-slate-400',
    chip: 'bg-slate-500/15 text-slate-700 dark:text-slate-300',
    ring: 'border-slate-400/30',
  },
}

export const PRIORITY_GUIDES = {
  A: {
    label: 'A-race',
    meaning: 'The anchor. Every phase is measured backward from this date.',
    accent: 'border-amber-400/40 bg-amber-500/10 text-amber-800 dark:text-amber-200',
    pin: 'bg-amber-400',
  },
  B: {
    label: 'B-race',
    meaning: 'Important tune-up. Gets a 3-day mini-taper before and easy days after.',
    accent: 'border-indigo-400/40 bg-indigo-500/10 text-indigo-800 dark:text-indigo-200',
    pin: 'bg-indigo-400',
  },
  C: {
    label: 'C-race',
    meaning: 'Treated as a hard workout. No taper, no extra rest.',
    accent: 'border-slate-400/30 bg-slate-500/10',
    pin: 'bg-slate-400',
  },
  D: {
    label: 'Test',
    meaning: 'A guided threshold test. Results can recalibrate your zones.',
    accent: 'border-teal-400/40 bg-teal-500/10 text-teal-800 dark:text-teal-200',
    pin: 'bg-teal-400',
  },
  E: {
    label: 'Event',
    meaning: 'On the calendar for awareness. No plan changes.',
    accent: 'border-[var(--aal-line)] bg-[var(--aal-accent-soft)]',
    pin: 'bg-slate-300',
  },
}

/** What each replan trigger actually means, in plain words. */
export const TRIGGER_GUIDES = {
  missed_key_sessions: {
    title: 'Key sessions missed',
    plain: 'Two or more quality sessions did not happen this week, so the remaining weeks are ahead of where you actually are.',
  },
  new_bc_race: {
    title: 'New race added',
    plain: 'A B or C race went on the calendar. Remaining volume needs to make room for it.',
  },
  active_injury: {
    title: 'Active injury on file',
    plain: 'A recovery week goes in first and the later phases shift back a week.',
  },
  sustained_high_acwr: {
    title: 'Load climbing too fast',
    plain: 'Your ACWR has been in the caution zone for two straight weeks. Remaining weeks get pulled back.',
  },
}

/**
 * A-race feasibility from your last completed B-race, projected with Riegel.
 * This is a read on your target time — never a reason to change the timeline.
 */
export const FEASIBILITY_GUIDES = {
  on_track: {
    label: 'On track',
    plain: 'Your last B-race projects to your A-race target. Peak can keep race-pace work as planned.',
    accent: 'border-emerald-500/35 bg-emerald-500/10 text-emerald-800 dark:text-emerald-200',
    chip: 'bg-emerald-500/15 text-emerald-700 dark:text-emerald-300',
  },
  stretch: {
    label: 'A stretch',
    plain: 'Your B-race projects a little slower than your target. The target is reachable but it is the optimistic end — keep Peak controlled.',
    accent: 'border-amber-500/35 bg-amber-500/10 text-amber-800 dark:text-amber-200',
    chip: 'bg-amber-500/15 text-amber-700 dark:text-amber-300',
  },
  unlikely: {
    label: 'Ambitious',
    plain: 'Your B-race projects well outside your target. Worth resetting the goal time rather than forcing the pace — Peak should build durability instead.',
    accent: 'border-rose-500/35 bg-rose-500/10 text-rose-800 dark:text-rose-200',
    chip: 'bg-rose-500/15 text-rose-700 dark:text-rose-300',
  },
  unknown: {
    label: 'No target set',
    plain: 'Add a target time to your A-race on Profile and we can project it from your B-race result.',
    accent: 'border-[var(--aal-line)] bg-[var(--aal-accent-soft)]',
    chip: 'bg-slate-500/15 text-slate-700 dark:text-slate-300',
  },
}

export function feasibilityGuide(value) {
  return FEASIBILITY_GUIDES[value] || FEASIBILITY_GUIDES.unknown
}

/** How much the plan's personalised limits can be trusted yet. */
export const CONFIDENCE_GUIDES = {
  high: {
    label: 'Based on your logged training',
    plain: 'You have enough recent sessions on record for these limits to reflect you rather than a default.',
  },
  medium: {
    label: 'Partly based on your history',
    plain: 'Some of this comes from your profile rather than logged sessions. It will sharpen as you record more training.',
  },
  low: {
    label: 'Starting from defaults',
    plain: 'There is no training history to read yet, so these limits start deliberately conservative and rise as you log sessions.',
  },
}

export function confidenceGuide(value) {
  return CONFIDENCE_GUIDES[value] || CONFIDENCE_GUIDES.low
}

/** 135 -> "2h 15m". Long-day ceilings read better in hours. */
export function formatMinutes(minutes) {
  const total = Number(minutes)
  if (!Number.isFinite(total) || total <= 0) return '—'
  const hours = Math.floor(total / 60)
  const mins = Math.round(total % 60)
  if (!hours) return `${mins} min`
  return mins ? `${hours}h ${mins}m` : `${hours}h`
}

/** The Rebuild vs Replan decision, spelled out for the confirm dialog. */
export const REBUILD_GUIDE = {
  title: 'Rebuild the whole season?',
  consequence:
    'This archives your current plan and draws every phase again starting from today. Weeks you have already finished will not stay on the timeline.',
  useWhen: [
    'Your A-race date or event changed',
    'You are starting a fresh season after your last A-race',
    'You have been away long enough that the old plan no longer reflects you',
  ],
  useReplanWhen: [
    'You missed sessions or are carrying an injury',
    'You added a B or C race',
    'Your training load has been climbing too fast',
  ],
  inputs: [
    'Your A-race date and target',
    'Your fitness level and typical session length',
    'Every B, C, D, and E event on your calendar',
    'Any injury, missed-session, or load signals active right now',
  ],
}

export const REPLAN_GUIDE = {
  title: 'Replan the remaining weeks?',
  consequence:
    'Phases you have already completed stay exactly as they are. Only the weeks from today to your A-race are redrawn.',
  reassurance: 'This is the safer of the two options and the one we recommend when training reality has shifted.',
}

export const SEASON_LEARN = [
  {
    id: 'retrograde',
    title: 'Why does the plan start from the race and work backward?',
    body: [
      'Race day is the only fixed point in your season, so the planner counts backward from it. That way the taper always lands in the right week and the phases share out whatever weeks genuinely remain.',
      'A generic 12-week template does the opposite: it starts today and finishes whenever it finishes, which is often the wrong week.',
    ],
    refs: [
      {
        label: 'Issurin VB. New horizons for the methodology and physiology of training periodization (2010)',
        href: 'https://pubmed.ncbi.nlm.nih.gov/20199120/',
        note: 'block periodization overview',
      },
    ],
  },
  {
    id: 'ratios',
    title: 'How are the phase lengths decided?',
    body: [
      'The taper and Peak are sized first, because both have a physiological ceiling: a taper longer than about three weeks starts costing fitness, and race-pace sharpening cannot be held for months. Whatever weeks remain are split roughly four-to-three between Base and Build.',
      'That is why a very long runway grows your Base rather than stretching your taper — extra aerobic weeks are worth more than extra sharpening weeks.',
      'Recovery weeks are taken out of Base and Build rather than added on top, so every fourth week is a down week and the total still lands exactly on race day. Short seasons and newer athletes get a compressed version, because the taper has to fit even when only a few weeks are left.',
    ],
    refs: [
      {
        label: 'Bosquet L et al. Effects of tapering on performance: a meta-analysis (2007)',
        href: 'https://pubmed.ncbi.nlm.nih.gov/17762377/',
        note: 'why the taper is capped at three weeks',
      },
    ],
  },
  {
    id: 'limits',
    title: 'Why is my long day capped where it is?',
    body: [
      'Each phase has a long-day ceiling, but yours is lowered to what you have actually done. We take the longest session you have logged in the last six weeks and allow a step up of no more than about 30 percent — the point where a durability session turns into an injury.',
      'The same reading sets how often you get a recovery week and whether volume is held back. An active injury, a masters age band, or a thin training history all shorten the loading cycle from four weeks to three.',
      'None of it is hidden: the exact reason for every number is listed under "Why these numbers" above, and the ceiling rises on its own as you log longer sessions.',
    ],
  },
  {
    id: 'fixed-race',
    title: 'What happens to my Peak when I replan?',
    body: [
      'Peak and taper are anchored to race day, so a replan keeps them at their full length. The weeks you lose come out of Base and Build instead — the part of the season that is furthest from the race and cheapest to shorten.',
      'Weeks you have already trained are never rewritten. A replan starts from the Monday of the current week and only redraws what is still ahead of you.',
    ],
  },
  {
    id: 'not-ai',
    title: 'Is this season written by AI?',
    body: [
      'No. The phase dates come from a deterministic periodization engine, so the same inputs always produce the same season and nothing drifts between visits.',
      'AI reads your season to write the individual weekly workouts and to explain the block you are in. It never invents the timeline.',
    ],
  },
  {
    id: 'move-week',
    title: 'Can I move a week from one phase to another?',
    body: [
      'Yes. Open a phase and give it a week or take one away. The week comes from — or goes to — a later block, so your A-race date never moves and weeks you have already finished stay as they were.',
      'Peak and taper always keep at least one week. Restore after the race is locked. That is the smallest edit that still respects the physiology the engine is built on.',
    ],
  },
  {
    id: 'replan',
    title: 'What makes the plan change?',
    body: [
      'Nothing changes silently. When you miss key sessions, log an injury, add a B or C race, or your load climbs too fast for two weeks, a Replan suggestion appears here.',
      'You decide whether to apply it. Replan keeps your finished weeks; Rebuild starts the whole timeline again from today.',
    ],
  },
  {
    id: 'taper',
    title: 'Why does volume drop so much at the end?',
    body: [
      'Fatigue clears much faster than fitness fades. Cutting volume 40 to 60 percent for one to two weeks while keeping a little intensity is one of the most reliably tested performance gains in endurance sport.',
    ],
    refs: [
      {
        label: 'Bosquet L et al. Effects of tapering on performance: a meta-analysis (2007)',
        href: 'https://pubmed.ncbi.nlm.nih.gov/17762377/',
        note: 'taper volume and duration',
      },
    ],
  },
]

export function phaseGuide(phaseType) {
  return PHASE_GUIDES[phaseType] || PHASE_GUIDES.base
}

export function phaseAccent(phaseType) {
  return PHASE_ACCENTS[phaseType] || PHASE_ACCENTS.base
}

export function phaseLabel(phaseType) {
  return PHASE_GUIDES[phaseType]?.label || String(phaseType || '').replace(/_/g, ' ')
}

export function toDate(value) {
  if (!value) return null
  const parsed = new Date(`${value}T12:00:00`)
  return Number.isNaN(parsed.getTime()) ? null : parsed
}

export function formatSeasonDate(value, { withYear = true } = {}) {
  const parsed = toDate(value)
  if (!parsed) return '—'
  return parsed.toLocaleDateString(undefined, {
    day: 'numeric',
    month: 'short',
    ...(withYear ? { year: 'numeric' } : {}),
  })
}

export function formatRange(start, end) {
  const sameYear = toDate(start)?.getFullYear() === toDate(end)?.getFullYear()
  return `${formatSeasonDate(start, { withYear: !sameYear })} – ${formatSeasonDate(end)}`
}

export function daysBetween(start, end) {
  const a = toDate(start)
  const b = toDate(end)
  if (!a || !b) return 0
  return Math.round((b - a) / 86400000)
}

/** Inclusive day span, minimum 1, for timeline widths. */
export function spanDays(start, end) {
  return Math.max(1, daysBetween(start, end) + 1)
}

export function daysUntil(value, from = new Date()) {
  const target = toDate(value)
  if (!target) return null
  const base = new Date(from.getFullYear(), from.getMonth(), from.getDate(), 12)
  return Math.round((target - base) / 86400000)
}

export function weeksUntil(value, from = new Date()) {
  const days = daysUntil(value, from)
  return days == null ? null : Math.max(0, Math.ceil(days / 7))
}

export function countdownLabel(value, from = new Date()) {
  const days = daysUntil(value, from)
  if (days == null) return '—'
  if (days < 0) return 'Race day has passed'
  if (days === 0) return 'Race day'
  if (days === 1) return 'Tomorrow'
  if (days < 14) return `${days} days out`
  const weeks = Math.round(days / 7)
  return `${weeks} weeks out`
}

/** Is `on` inside the phase window? Dates are ISO day strings. */
export function isCurrentPhase(phase, on = new Date()) {
  const start = toDate(phase?.start_date)
  const end = toDate(phase?.end_date)
  if (!start || !end) return false
  const today = new Date(on.getFullYear(), on.getMonth(), on.getDate(), 12)
  return start <= today && today <= end
}

/** 0-100 position of today across the whole season, or null when outside it. */
/** ISO Monday on or before the given day. */
export function mondayOf(value) {
  const parsed = toDate(value)
  if (!parsed) return null
  const day = parsed.getDay()
  const diff = day === 0 ? -6 : 1 - day
  parsed.setDate(parsed.getDate() + diff)
  return parsed.toISOString().slice(0, 10)
}

/** Map a horizontal position (0–100%) on the season bar to a week-start Monday. */
export function weekStartFromTimelinePct(startDate, endDate, pct) {
  const total = spanDays(startDate, endDate)
  const offsetDays = Math.round((Math.max(0, Math.min(100, pct)) / 100) * total)
  const anchor = toDate(startDate)
  if (!anchor) return null
  anchor.setDate(anchor.getDate() + offsetDays)
  return mondayOf(anchor.toISOString().slice(0, 10))
}

export function todayPositionPct(startDate, endDate, on = new Date()) {
  const total = spanDays(startDate, endDate)
  const elapsed = daysBetween(startDate, on.toISOString().slice(0, 10))
  if (total <= 0) return null
  const pct = (elapsed / total) * 100
  if (pct < 0 || pct > 100) return null
  return pct
}

export function intensityLabel(bias) {
  const value = String(bias || '').toLowerCase()
  if (value === 'low') return 'Easy week'
  if (value === 'moderate') return 'Mixed week'
  if (value === 'high') return 'Hard week'
  return '—'
}

export function volumeBiasLabel(bias) {
  if (bias == null) return '—'
  const value = Number(bias)
  if (value >= 1.05) return 'Above your usual'
  if (value >= 0.95) return 'Around your usual'
  if (value >= 0.7) return 'Below your usual'
  return 'Well below usual'
}
