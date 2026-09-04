/** Daily stress vs your usual day. Scale is 0.70–1.40 of the 7-day mean. Higher = more load. */

export const STRESS_SCALE = { min: 0.7, max: 1.4 }
export const STRESS_HIGH_ABSOLUTE = 70

export const STRESS_ZONES = [
  {
    id: 'quiet',
    from: 0.7,
    to: 0.9,
    label: 'Quiet',
    range: 'below 90% of usual',
    color: '#14B8A6',
    meaning:
      'Today’s all-day stress sat well below your recent average. The system looks less “on” than usual — often a recovery day, a quieter calendar, or less life load. It is not a fitness score.',
    workouts:
      'Train as planned if sleep and HRV agree. Do not add a surprise hard session just because stress looks low.',
    improve:
      'Keep the habits that produced the quiet day. If stress is always this low while you are trying to build fitness, check that you are actually training.',
  },
  {
    id: 'typical',
    from: 0.9,
    to: 1.1,
    label: 'Typical',
    range: '90 – 110% of usual',
    color: '#5B8DEF',
    meaning:
      'Close to your own recent days. For COROS stress, “normal for you” matters more than matching another athlete’s 0–100 number.',
    workouts:
      'Keep planned quality if sleep and legs agree. Do not stack extra life stress (late nights, travel) on top of a hard session.',
    improve:
      'Watch streaks, not single days. Typical stress with falling HRV or short sleep is still a cue to protect tonight.',
  },
  {
    id: 'elevated',
    from: 1.1,
    to: 1.25,
    label: 'Elevated',
    range: '110 – 125% of usual',
    color: '#F59E0B',
    meaning:
      'Noticeably above your 7-day average. All-day sympathetic load is up — training, work, travel, heat, or a short night can all do this. One day is often noise; two or three is accumulated load.',
    workouts:
      'Hold easy days. Shorten or skip quality. Keep anything you do conversational. Do not add a new workout type.',
    improve:
      'Protect sleep first. Cut caffeine late, trim non-training stress where you can, and let tomorrow be easier than today.',
  },
  {
    id: 'high',
    from: 1.25,
    to: 1.4,
    label: 'High',
    range: 'above 125% of usual, or 70+',
    color: '#FB7185',
    meaning:
      'A clear spike versus your usual, or an absolute reading at 70+ (our safety flag). This is allostatic load showing up in the daily average — a back-off signal, not a diagnosis of anxiety or overtraining.',
    workouts:
      'Easy movement or rest. Skip intervals, races, and heavy strength. Tomorrow should not “make up” today’s missed quality.',
    improve:
      'Sleep, food, and a quieter calendar beat extra easy kilometres. Recheck HRV and resting HR; if those are also off, keep the easy days going.',
  },
]

export const STRESS_LEARN = [
  {
    id: 'what',
    title: 'What is daily stress?',
    body: [
      'On this page, stress is COROS’s all-day average of how “on” your body was — a 0–100 style score from heart-rate and HRV patterns across waking hours, not a psychology questionnaire and not training-load TRIMP.',
      'It mixes training, work, travel, heat, caffeine, and poor recovery into one daily number. That is useful and coarse: a hard meeting and a hard interval can look similar.',
    ],
    refs: [
      {
        label: 'McEwen BS. Physiology and neurobiology of stress and adaptation (2007)',
        href: 'https://journals.physiology.org/doi/full/10.1152/physrev.00041.2006',
        note: 'allostasis: load that is useful until it is not',
      },
    ],
  },
  {
    id: 'usual',
    title: 'What is “usual” stress on this page?',
    body: [
      'Usual = the average of your last 7 days with a stress value. Today ÷ that average is “vs usual.” 1.00 means you matched the week. 1.20 means about 20% more all-day load than you have been carrying.',
      'Unlike HRV (where higher is often better), higher stress vs usual is the caution direction. A quiet week can make a normal day look “elevated,” so we also flag any day at 70+ regardless of the ratio.',
    ],
    refs: [
      {
        label: 'IOC consensus: load in sport and risk of illness (Soligard et al., 2016, Part 2)',
        href: 'https://bjsm.bmj.com/content/50/17/1043',
        note: 'life load, travel, and illness risk sit beside training load',
      },
    ],
  },
  {
    id: 'zones',
    title: 'How to read the zones',
    body: [
      'The strip is not ACWR and not the HRV bands. Quiet is below ~90% of your usual, typical is about 90–110%, elevated 110–125%, high above that. A raw score of 70 or more is treated as high even if the ratio looks modest — that matches our coach safety rule.',
      'Garmin-style charts often label 0–25 rest, 26–50 low, 51–75 medium, 76–100 high on the absolute 0–100 scale. COROS is in the same family. Your 7-day usual is still the better personal lens.',
    ],
    refs: [
      {
        label: 'Laborde S, Mosley E, Thayer JF. Heart rate variability and cardiac vagal tone (2017)',
        href: 'https://pmc.ncbi.nlm.nih.gov/articles/PMC5624990/',
        note: 'why all-day autonomic scores move with life load, not only workouts',
      },
    ],
  },
  {
    id: 'vs-hrv',
    title: 'How is this different from HRV?',
    body: [
      'HRV on this app is overnight (sleep). Stress here is an all-day average. They often move together — a smashed day raises daytime stress and can suppress the next night’s HRV — but they can split: a stressful workday with an easy workout, or a hard session on an otherwise calm calendar.',
      'Read both. Overnight HRV asks “did I absorb yesterday?” Daily stress asks “how loaded was today, including life?”',
    ],
    refs: [
      {
        label: 'Buchheit M. Monitoring training status with HR measures (2014)',
        href: 'https://pmc.ncbi.nlm.nih.gov/articles/PMC4120687/',
        note: 'standardized autonomic measures; context still required',
      },
    ],
  },
  {
    id: 'why',
    title: 'Why it matters for workouts',
    body: [
      'High non-training load (work, travel, illness, short sleep) raises injury and illness risk even when the training plan looks moderate. That is the point of the IOC load-and-health statements: the body does not separate “life stress” from “session stress.”',
      'Use a high or elevated day to cut intensity first, not to add extra easy kilometres that keep the score high. Pair it with sleep, HRV, and how you feel.',
    ],
    refs: [
      {
        label: 'Soligard T et al. IOC consensus on load and illness (BJSM, 2016)',
        href: 'https://bjsm.bmj.com/content/50/17/1043.full.pdf',
        note: 'PDF of Part 2',
      },
    ],
  },
  {
    id: 'calc',
    title: 'How this page calculates it',
    body: [
      'Today = the newest COROS daily average stress. 7-day usual = mean of up to the last 7 days that have a value. Vs usual = today ÷ 7-day mean (blank until a usual day exists).',
      'The chart is the daily series. The dashed line is that 7-day mean. Explore history pulls a wider COROS window when the cache is thin.',
    ],
    refs: [
      {
        label: 'McEwen BS. Protective and damaging effects of stress mediators (1998 overview)',
        href: 'https://pubmed.ncbi.nlm.nih.gov/9457596/',
        note: 'allostatic load as a concept, not a COROS formula',
      },
      {
        label: 'COROS EvoLab',
        href: 'https://support.coros.com/hc/en-us/articles/4412789816724-EvoLab',
        note: 'how COROS frames recovery and training status',
      },
    ],
  },
  {
    id: 'limits',
    title: 'What it cannot tell you',
    body: [
      'This is not a diagnosis of anxiety, overtraining, or burnout. Caffeine, heat, alcohol, illness, and a tight watch strap all move the number. It does not measure muscle damage or a niggle.',
      'A “typical” stress day with poor sleep is still a poor-sleep day. A high stress day after a planned race can be expected. Do not chase a lower number with extra easy volume that keeps you on your feet all afternoon.',
    ],
    refs: [
      {
        label: 'IOC consensus: load, health, and illness (2016)',
        href: 'https://bjsm.bmj.com/content/50/17/1043',
      },
    ],
  },
]

function mean(values) {
  const list = values.filter((value) => value != null && !Number.isNaN(Number(value)))
  if (!list.length) return null
  return list.reduce((sum, value) => sum + Number(value), 0) / list.length
}

export function stressRatio(today, usual) {
  if (today == null || usual == null || Number(usual) <= 0) return null
  return Number(today) / Number(usual)
}

export function stressMarkerPercent(ratio) {
  if (ratio == null || Number.isNaN(Number(ratio))) return null
  const { min, max } = STRESS_SCALE
  return Math.min(100, Math.max(0, ((Number(ratio) - min) / (max - min)) * 100))
}

export function getStressZone(ratio, today = null) {
  if (today != null && Number(today) >= STRESS_HIGH_ABSOLUTE) return STRESS_ZONES[3]
  if (ratio == null || Number.isNaN(Number(ratio))) {
    return { id: 'empty', label: 'Need more days', color: '#94a3b8' }
  }
  const value = Number(ratio)
  if (value < 0.9) return STRESS_ZONES[0]
  if (value < 1.1) return STRESS_ZONES[1]
  if (value < 1.25) return STRESS_ZONES[2]
  return STRESS_ZONES[3]
}

export function interpretStress({ today, usual7, usual28, days }) {
  const ratio = stressRatio(today, usual7)
  const zone = getStressZone(ratio, today)
  const zoneGuide = STRESS_ZONES.find((item) => item.id === zone.id) || null
  const pts = (value) => (value == null ? '—' : `${Math.round(Number(value))}`)

  if (zone.id === 'empty') {
    return {
      zone,
      zoneGuide: null,
      ratio,
      headline: 'We need a few days to find your usual',
      body: 'Daily stress only becomes a traffic light once there is a 7-day average. Keep syncing COROS — after a week this page can tell you whether today was quiet, typical, or a spike.',
    }
  }

  const copy = {
    quiet: {
      headline: 'A quieter day than your usual',
      body: `${pts(today)} vs a 7-day usual of ${pts(usual7)} (${Number(ratio).toFixed(2)}×). Useful after a hard block; do not treat it as a licence to pile on extra work.`,
    },
    typical: {
      headline: 'Right around your usual day',
      body: `${pts(today)} vs ${pts(usual7)} (${Number(ratio).toFixed(2)}×). Train as planned if sleep and HRV agree.`,
    },
    elevated: {
      headline: 'Above your recent average',
      body: `${pts(today)} against ${pts(usual7)} usual (${Number(ratio).toFixed(2)}×). Ease intensity until days return toward typical.`,
    },
    high: {
      headline: 'Stress spiked — this is a back-off day',
      body: `${pts(today)} vs ${pts(usual7)} (${ratio != null ? `${Number(ratio).toFixed(2)}×` : 'no usual yet'}). Cut quality. A 70+ reading is our safety flag even if the week’s average is also high.`,
    },
  }

  const selected = copy[zone.id] || copy.typical
  return {
    zone,
    zoneGuide,
    ratio,
    days: days || 0,
    usual28,
    headline: selected.headline,
    body: selected.body,
  }
}

export function summarizeStressPoints(points) {
  const valued = (points || [])
    .filter((point) => point.value != null && point.date)
    .sort((a, b) => String(a.date).localeCompare(String(b.date)))
  const last = valued.length ? valued[valued.length - 1] : null
  const last7 = valued.slice(-7).map((point) => Number(point.value))
  const last28 = valued.slice(-28).map((point) => Number(point.value))
  return {
    today: last?.value ?? null,
    lastDate: last?.date ?? null,
    usual7: mean(last7),
    usual28: mean(last28),
    days: valued.length,
    valued,
  }
}
