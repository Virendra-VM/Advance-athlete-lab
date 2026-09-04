/** Daily steps vs your usual day. Scale is 0.50–1.80 of the 7-day mean. Quiet and very high are both cautions. */

export const DAILY_SCALE = { min: 0.5, max: 1.8 }
export const DAILY_SEDENTARY_STEPS = 5000

export const DAILY_ZONES = [
  {
    id: 'quiet',
    from: 0.5,
    to: 0.75,
    label: 'Quiet',
    range: 'below 75% of usual, or under 5,000',
    color: '#F59E0B',
    meaning:
      'Today’s incidental movement sat well below your recent average, or under the 5,000-step mark often labelled sedentary in step-count research. A planned rest day can look like this. A streak of quiet days with no recovery intent is low NEAT — not the same as GPS training volume.',
    workouts:
      'If this is a recovery day, keep sessions easy and let the low step count stand. If you sat all day by accident, a walk helps more than extra intervals.',
    improve:
      'Add easy walking, standing breaks, or an errand on foot. Do not “fix” a quiet day with a surprise hard session.',
  },
  {
    id: 'typical',
    from: 0.75,
    to: 1.2,
    label: 'Typical',
    range: '75 – 120% of usual',
    color: '#5B8DEF',
    meaning:
      'Close to your own recent days. For steps, “normal for you” matters more than hitting someone else’s 10,000. Calories on this page are the energy companion — they often rise with steps, heat, and training.',
    workouts:
      'Train as planned if sleep and HRV agree. On quality days, try not to stack a huge incidental walk on top of the session.',
    improve:
      'Keep the baseline movement that produced this week. Watch streaks of quiet or very-high days more than a single number.',
  },
  {
    id: 'busy',
    from: 1.2,
    to: 1.5,
    label: 'Busy',
    range: '120 – 150% of usual',
    color: '#14B8A6',
    meaning:
      'Noticeably more on-foot load than your 7-day average — travel, a long workday on your feet, sightseeing, or a big easy-walk day. Useful movement. It still costs recovery when it sits beside a hard workout.',
    workouts:
      'Keep planned easy days easy. If quality is on the calendar, shorten it or protect the hours after the session — do not add a long afternoon walk “for extra steps.”',
    improve:
      'Busy is fine as general health. The coaching question is stacking: busy steps + intervals is two loads in one day.',
  },
  {
    id: 'high',
    from: 1.5,
    to: 1.8,
    label: 'Very high',
    range: 'above 150% of usual',
    color: '#FB7185',
    meaning:
      'A clear spike versus your usual incidental day. Theme parks, airports, moving house, or a 25 km walk will all do this. The body does not separate “life steps” from “session steps” when it is time to recover.',
    workouts:
      'Easy movement or rest if a hard session is also planned. Skip stacking intervals or a long run on the same calendar day.',
    improve:
      'Let tomorrow be quieter. Food and sleep beat extra easy kilometres that keep the step count high.',
  },
]

export const DAILY_LEARN = [
  {
    id: 'what',
    title: 'What is daily health on this page?',
    body: [
      'The traffic light is COROS daily steps versus your own 7-day usual — incidental movement (walking, standing around, errands), not GPS training kilometres and not COROS effort load. Calories are the energy companion. Average HR across the day is a third signal: how hard the heart worked through that movement and any workouts.',
      'Steps mix life and training. A long easy walk and a race expo can look the same on this chart. That is useful and coarse.',
    ],
    refs: [
      {
        label: 'Levine JA. Non-exercise activity thermogenesis (NEAT)',
        href: 'https://pubmed.ncbi.nlm.nih.gov/12468415/',
        note: 'incidental movement is a real energy and load term',
      },
    ],
  },
  {
    id: 'usual',
    title: 'What is “usual” here?',
    body: [
      'Usual = the average of your last 7 days with a step count. Today ÷ that average is “vs usual.” 1.00 means you matched the week. 1.40 means about 40% more incidental walking than you have been doing.',
      'Unlike HRV (higher often better) and unlike stress (higher is caution), both tails matter: too quiet is low NEAT; very high is extra life load on top of training. A quiet week can make a normal day look “busy,” so we also flag any day under 5,000 steps regardless of the ratio.',
    ],
    refs: [
      {
        label: 'Tudor-Locke C, Bassett DR. How many steps/day are enough? (2004)',
        href: 'https://pubmed.ncbi.nlm.nih.gov/14715035/',
        note: '<5,000 steps often labelled sedentary; 10,000 is a slogan, not a law',
      },
    ],
  },
  {
    id: 'zones',
    title: 'How to read the zones',
    body: [
      'The strip is not ACWR and not the Stress 0–100 bands. Quiet is below ~75% of your usual (or under 5,000 steps), typical about 75–120%, busy 120–150%, very high above that. Step counts swing more than resting HR, so the scale is wider (0.50–1.80).',
      'Population charts often cite 7,000–10,000 steps. Your 7-day usual is still the better personal lens — an ultra week and a desk week should not share one absolute target.',
    ],
    refs: [
      {
        label: 'Paluch AE et al. Daily steps and mortality (JAMA Network Open, 2022)',
        href: 'https://jamanetwork.com/journals/jamanetworkopen/fullarticle/2791422',
        note: 'open access; benefits accrue well below 10,000 for many adults',
      },
    ],
  },
  {
    id: 'calories',
    title: 'Where do calories and average HR fit?',
    body: [
      'Calories here are COROS’s daily energy estimate — movement plus basal burn, not a food log. They usually rise with steps, workouts, and heat. Use them as a companion, not a second traffic light.',
      'Day-average HR rises with sessions, hills, heat, caffeine, and stress. A busy step day with a calm average HR is often easy walking. The same steps with a high average HR may have included a workout or a hot, rushed day.',
    ],
    refs: [
      {
        label: 'Achten J, Jeukendrup AE. Heart rate monitoring (Sports Medicine, 2003)',
        href: 'https://pubmed.ncbi.nlm.nih.gov/12617692/',
        note: 'HR reflects demand, not only fitness',
      },
    ],
  },
  {
    id: 'vs-volume',
    title: 'How is this different from Volume & ACWR?',
    body: [
      'Volume on this app is GPS distance from structured activities. Daily Health is all-day steps, including the walk to the shop. You can have a low kilometre week and a very high step week (travel), or a high run week with quiet steps (drive everywhere, train, sit).',
      'Read both. Kilometres ask “did I jump the training dose?” Steps ask “how much incidental load did life add?”',
    ],
    refs: [
      {
        label: 'IOC consensus: load in sport and risk of illness (Soligard et al., 2016, Part 2)',
        href: 'https://bjsm.bmj.com/content/50/17/1043',
        note: 'life load and travel sit beside training load',
      },
    ],
  },
  {
    id: 'why',
    title: 'Why it matters for workouts',
    body: [
      'High non-training movement (work on your feet, travel, sightseeing) raises fatigue even when the training plan looks moderate. Very low movement can leave you stiff and under-recovered in a different way. Cut intensity first on a very-high step day; add a walk, not intervals, on an accidentally quiet day.',
      'WHO activity guidance is about weekly movement for health. This page is the athlete version: your usual vs today, next to the session plan.',
    ],
    refs: [
      {
        label: 'WHO. Physical activity fact sheet (2020 guidelines)',
        href: 'https://www.who.int/news-room/fact-sheets/detail/physical-activity',
        note: 'population health targets; not an ACWR formula',
      },
      {
        label: 'Ekelund U et al. Physical activity and mortality (Lancet, 2016)',
        href: 'https://www.thelancet.com/journals/lancet/article/PIIS0140-6736(16)30370-1/fulltext',
        note: 'more daily movement associates with lower mortality in cohorts',
      },
    ],
  },
  {
    id: 'calc',
    title: 'How this page calculates it',
    body: [
      'Today = the newest COROS daily step count. 7-day usual = mean of up to the last 7 days that have a value. Vs usual = today ÷ 7-day mean (blank until a usual day exists). Under 5,000 steps is treated as quiet even if the ratio looks typical.',
      'The main chart is steps (indigo) with calories (rose) as a companion. The dashed line is the 7-day step mean. Average HR is a second chart in the same date window. Explore history pulls a wider COROS window when the cache is thin.',
    ],
    refs: [
      {
        label: 'COROS EvoLab',
        href: 'https://support.coros.com/hc/en-us/articles/4412789816724-EvoLab',
        note: 'how COROS frames recovery and daily status',
      },
    ],
  },
  {
    id: 'limits',
    title: 'What it cannot tell you',
    body: [
      'This is not a food diary, not a VO₂ test, and not GPS distance. Wrist step counts miss some cycling and over-count fidgeting. Calories are estimates. A “typical” step day with poor sleep is still a poor-sleep day.',
      'Do not chase 10,000 on a recovery day that was supposed to be quiet. Do not treat a very-high travel day as free fitness.',
    ],
    refs: [
      {
        label: 'Tudor-Locke C, Bassett DR. Steps/day indices (2004)',
        href: 'https://pubmed.ncbi.nlm.nih.gov/14715035/',
      },
    ],
  },
]

function mean(values) {
  const list = values.filter((value) => value != null && !Number.isNaN(Number(value)))
  if (!list.length) return null
  return list.reduce((sum, value) => sum + Number(value), 0) / list.length
}

export function dailyRatio(today, usual) {
  if (today == null || usual == null || Number(usual) <= 0) return null
  return Number(today) / Number(usual)
}

export function dailyMarkerPercent(ratio) {
  if (ratio == null || Number.isNaN(Number(ratio))) return null
  const { min, max } = DAILY_SCALE
  return Math.min(100, Math.max(0, ((Number(ratio) - min) / (max - min)) * 100))
}

export function getDailyZone(ratio, today = null) {
  if (today != null && Number(today) < DAILY_SEDENTARY_STEPS) return DAILY_ZONES[0]
  if (ratio == null || Number.isNaN(Number(ratio))) {
    return { id: 'empty', label: 'Need more days', color: '#94a3b8' }
  }
  const value = Number(ratio)
  if (value < 0.75) return DAILY_ZONES[0]
  if (value < 1.2) return DAILY_ZONES[1]
  if (value < 1.5) return DAILY_ZONES[2]
  return DAILY_ZONES[3]
}

export function interpretDaily({ today, usual7, usual28, calories, calories7, days }) {
  const ratio = dailyRatio(today, usual7)
  const zone = getDailyZone(ratio, today)
  const zoneGuide = DAILY_ZONES.find((item) => item.id === zone.id) || null
  const steps = (value) =>
    value == null ? '—' : `${Math.round(Number(value)).toLocaleString('en-US')}`

  if (zone.id === 'empty') {
    return {
      zone,
      zoneGuide: null,
      ratio,
      headline: 'We need a few days to find your usual',
      body: 'Daily steps only become a traffic light once there is a 7-day average. Keep syncing COROS — after a week this page can tell you whether today was quiet, typical, busy, or a spike.',
    }
  }

  const copy = {
    quiet: {
      headline:
        today != null && Number(today) < DAILY_SEDENTARY_STEPS
          ? 'Under 5,000 steps — a quiet day'
          : 'A quieter movement day than your usual',
      body: `${steps(today)} steps vs a 7-day usual of ${steps(usual7)} (${
        ratio != null ? `${Number(ratio).toFixed(2)}×` : 'no usual yet'
      }). Fine as a planned rest day; a streak of quiet days is low incidental load.`,
    },
    typical: {
      headline: 'Right around your usual day',
      body: `${steps(today)} vs ${steps(usual7)} steps (${Number(ratio).toFixed(2)}×). Train as planned if sleep agrees.`,
    },
    busy: {
      headline: 'More on your feet than usual',
      body: `${steps(today)} against ${steps(usual7)} usual (${Number(ratio).toFixed(2)}×). Useful movement — do not stack a hard session on top without shortening it.`,
    },
    high: {
      headline: 'Incidental load spiked — watch stacking',
      body: `${steps(today)} vs ${steps(usual7)} (${ratio != null ? `${Number(ratio).toFixed(2)}×` : 'no usual yet'}). Cut quality if a hard workout is also planned. Life steps still cost recovery.`,
    },
  }

  const selected = copy[zone.id] || copy.typical
  return {
    zone,
    zoneGuide,
    ratio,
    days: days || 0,
    usual28,
    calories,
    calories7,
    headline: selected.headline,
    body: selected.body,
  }
}

export function summarizeDailyPoints(points) {
  const valued = (points || [])
    .filter((point) => point.value != null && point.date)
    .sort((a, b) => String(a.date).localeCompare(String(b.date)))
  const last = valued.length ? valued[valued.length - 1] : null
  const last7 = valued.slice(-7)
  const last28 = valued.slice(-28)
  return {
    today: last?.value ?? null,
    lastDate: last?.date ?? null,
    calories: last?.secondary ?? null,
    usual7: mean(last7.map((point) => Number(point.value))),
    usual28: mean(last28.map((point) => Number(point.value))),
    calories7: mean(last7.map((point) => point.secondary).filter((value) => value != null)),
    days: valued.length,
    valued,
  }
}

export function summarizeAvgHrPoints(points) {
  const valued = (points || [])
    .filter((point) => point.value != null && point.date)
    .sort((a, b) => String(a.date).localeCompare(String(b.date)))
  const last = valued.length ? valued[valued.length - 1] : null
  const last7 = valued.slice(-7).map((point) => Number(point.value))
  return {
    today: last?.value ?? null,
    lastDate: last?.date ?? null,
    usual7: mean(last7),
    days: valued.length,
  }
}
