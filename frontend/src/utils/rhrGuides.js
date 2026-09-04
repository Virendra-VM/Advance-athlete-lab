/** Resting HR vs your usual night. Scale is 0.88–1.16 of the 7-day mean. Higher = more caution. */

export const RHR_SCALE = { min: 0.88, max: 1.16 }
export const RHR_RISE_SOFT = 5
export const RHR_RISE_HARD = 7

export const RHR_ZONES = [
  {
    id: 'below',
    from: 0.88,
    to: 0.97,
    label: 'Below usual',
    range: 'below 97% of usual',
    color: '#14B8A6',
    meaning:
      'Last night’s resting HR sat below your recent average. That is often a recovered or fitter night — more parasympathetic tone, or the aerobic engine adapting. It is not a VO₂ score, and a single low morning is not a licence to pile on work.',
    workouts:
      'Train as planned if sleep and HRV agree. Do not add a surprise long + hard day just because resting HR looks quiet.',
    improve:
      'Keep the sleep window and easy aerobic that produced this night. A long-term drift down is fitness; a sudden crash with poor sleep still needs context.',
  },
  {
    id: 'typical',
    from: 0.97,
    to: 1.05,
    label: 'Typical',
    range: '97 – 105% of usual',
    color: '#5B8DEF',
    meaning:
      'Close to your own recent nights. Resting HR is highly individual — 48 bpm for you is not comparable to 62 for someone else. “Normal for you” is the useful zone.',
    workouts:
      'Keep planned quality if sleep and legs agree. Watch streaks, not a single beat.',
    improve:
      'Pair it with overnight HRV. Typical RHR with falling HRV or short sleep is still a cue to protect tonight.',
  },
  {
    id: 'high',
    from: 1.05,
    to: 1.08,
    label: 'A little high',
    range: '105 – 108% of usual, or +5 bpm',
    color: '#F59E0B',
    meaning:
      'A few beats above your 7-day average — enough to notice, not a diagnosis. One night is often alcohol, heat, a late meal, or residual load. Two or three in a row, especially with suppressed HRV, is accumulated fatigue.',
    workouts:
      'Hold easy days. Shorten or skip quality. Keep anything you do conversational.',
    improve:
      'Protect sleep first. Recheck HRV and how you feel. Do not add extra easy kilometres to “flush” a high morning.',
  },
  {
    id: 'elevated',
    from: 1.08,
    to: 1.16,
    label: 'Elevated',
    range: 'above 108% of usual, or +7 bpm',
    color: '#FB7185',
    meaning:
      'A clear rise versus your usual, or about 7+ bpm above the week. Coaching research treats a sustained resting-HR increase as a recovery flag — illness, overload, travel, or a smashed night. It is not a medical reading.',
    workouts:
      'Easy movement or rest. Skip intervals, races, and heavy strength. Tomorrow should not “make up” today’s missed quality.',
    improve:
      'Sleep, food, and a quieter calendar. If HRV and stress are also off, keep the easy days going until resting HR is back near usual.',
  },
]

export const RHR_LEARN = [
  {
    id: 'what',
    title: 'What is resting HR?',
    body: [
      'On this page, resting HR is COROS’s overnight / first-thing heart rate in beats per minute — how slowly the heart is beating when you are not training. Endurance training often lowers the long-term baseline; last night versus your own week is the useful traffic light.',
      'It is a cheap, noisy autonomic marker. Caffeine, alcohol, heat, illness, altitude, and a tight strap all move it. Fitter is not “whoever has 40 bpm.”',
    ],
    refs: [
      {
        label: 'Buchheit M. Monitoring training status with HR measures (2014)',
        href: 'https://pmc.ncbi.nlm.nih.gov/articles/PMC4120687/',
        note: 'open access; why RHR and HRV must be standardized and individual',
      },
    ],
  },
  {
    id: 'usual',
    title: 'What is “usual” resting HR on this page?',
    body: [
      'Usual = the average of your last 7 days with a resting HR value. Last night ÷ that average is “vs usual.” 1.00 means you matched the week. 1.08 means about 8% higher than you have been running — a few extra beats for most athletes.',
      'Unlike HRV (where higher is often better), higher resting HR vs usual is the caution direction. A very quiet week can make a normal night look “a little high,” so we also flag a rise of about 5 bpm, and treat about 7+ bpm as elevated even if the ratio looks modest.',
    ],
    refs: [
      {
        label: 'Bellenger CR et al. Monitoring athletic training status through autonomic HR measures (2016)',
        href: 'https://pmc.ncbi.nlm.nih.gov/articles/PMC4960283/',
        note: 'meta-analysis: parasympathetic markers track functional overreaching',
      },
    ],
  },
  {
    id: 'zones',
    title: 'How to read the zones',
    body: [
      'The strip is not ACWR and not the Stress 0–100 bands. Below usual is under ~97% of your 7-day mean, typical about 97–105%, a little high 105–108% (or +5 bpm), elevated above that (or +7 bpm). Resting HR is more stable than daily stress, so the bands are tighter.',
      'A 5 bpm bump on a 50 bpm athlete is 10%; on a 70 bpm athlete it is about 7%. That is why we use both the ratio and the raw beat delta.',
    ],
    refs: [
      {
        label: 'Achten J, Jeukendrup AE. Heart rate monitoring (Sports Medicine, 2003)',
        href: 'https://pubmed.ncbi.nlm.nih.gov/12617692/',
        note: 'RHR as a practical training-status marker; still individual',
      },
    ],
  },
  {
    id: 'vs-hrv',
    title: 'How is this different from HRV and stress?',
    body: [
      'HRV is beat-to-beat variation overnight (milliseconds). Resting HR is the average overnight rate (bpm). They often move together — a smashed day can raise RHR and suppress HRV — but they can split: a high RHR with a typical HRV night, or the reverse.',
      'Daily stress on this app is an all-day 0–100 style score. Resting HR is a sleep/morning snapshot. Read HRV for “did I absorb yesterday?”, RHR for “is the engine still running hot?”, stress for “how loaded was today, including life?”',
    ],
    refs: [
      {
        label: 'Buchheit M. Monitoring training status with HR measures (2014)',
        href: 'https://pmc.ncbi.nlm.nih.gov/articles/PMC4120687/',
        note: 'use more than one HR-derived marker',
      },
    ],
  },
  {
    id: 'why',
    title: 'Why it matters for workouts',
    body: [
      'A rise in resting HR with falling HRV is a classic overreaching pattern in the monitoring literature. It does not diagnose illness, but it is a reason to cut intensity until nights return toward your usual — especially with poor sleep or high all-day stress.',
      'Use an elevated or a-little-high night to drop quality first, not to add extra easy kilometres. Pair it with how you feel; a planned race week can look “high” on purpose.',
    ],
    refs: [
      {
        label: 'Bellenger CR et al. Autonomic HR measures and training status (2016)',
        href: 'https://pmc.ncbi.nlm.nih.gov/articles/PMC4960283/',
      },
    ],
  },
  {
    id: 'calc',
    title: 'How this page calculates it',
    body: [
      'Last night = the newest COROS resting HR. 7-day usual = mean of up to the last 7 days that have a value. Vs usual = last night ÷ 7-day mean (blank until a usual night exists). A rise of 5 bpm vs usual is treated as at least “a little high”; 7+ bpm is elevated.',
      'The chart is the daily series. The dashed line is that 7-day mean. Explore history pulls a wider COROS window when the cache is thin.',
    ],
    refs: [
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
      'This is not a medical heart-rate reading, not a diagnosis of overtraining, and not your max HR. Late caffeine, alcohol, illness, altitude, and a watch that did not sit still all move the number. It does not measure a niggle or muscle damage.',
      'A “typical” resting HR with poor sleep is still a poor-sleep night. Do not chase a lower bpm with extra easy volume that keeps you on your feet all afternoon.',
    ],
    refs: [
      {
        label: 'Buchheit M. Monitoring training status with HR measures (2014)',
        href: 'https://pmc.ncbi.nlm.nih.gov/articles/PMC4120687/',
      },
    ],
  },
]

function mean(values) {
  const list = values.filter((value) => value != null && !Number.isNaN(Number(value)))
  if (!list.length) return null
  return list.reduce((sum, value) => sum + Number(value), 0) / list.length
}

export function rhrRatio(today, usual) {
  if (today == null || usual == null || Number(usual) <= 0) return null
  return Number(today) / Number(usual)
}

export function rhrDelta(today, usual) {
  if (today == null || usual == null) return null
  return Number(today) - Number(usual)
}

export function rhrMarkerPercent(ratio) {
  if (ratio == null || Number.isNaN(Number(ratio))) return null
  const { min, max } = RHR_SCALE
  return Math.min(100, Math.max(0, ((Number(ratio) - min) / (max - min)) * 100))
}

export function getRhrZone(ratio, today = null, usual = null) {
  const delta = rhrDelta(today, usual)
  if (delta != null && delta >= RHR_RISE_HARD) return RHR_ZONES[3]
  if (ratio == null || Number.isNaN(Number(ratio))) {
    return { id: 'empty', label: 'Need more nights', color: '#94a3b8' }
  }
  const value = Number(ratio)
  let zone = RHR_ZONES[3]
  if (value < 0.97) zone = RHR_ZONES[0]
  else if (value < 1.05) zone = RHR_ZONES[1]
  else if (value < 1.08) zone = RHR_ZONES[2]
  if (delta != null && delta >= RHR_RISE_SOFT && zone.id !== 'elevated' && zone.id !== 'high') {
    return RHR_ZONES[2]
  }
  return zone
}

export function interpretRhr({ today, usual7, usual28, days }) {
  const ratio = rhrRatio(today, usual7)
  const delta = rhrDelta(today, usual7)
  const zone = getRhrZone(ratio, today, usual7)
  const zoneGuide = RHR_ZONES.find((item) => item.id === zone.id) || null
  const bpm = (value) => (value == null ? '—' : `${Math.round(Number(value))} bpm`)
  const deltaLabel =
    delta == null ? '' : ` (${delta >= 0 ? '+' : ''}${Math.round(delta)} bpm vs usual)`

  if (zone.id === 'empty') {
    return {
      zone,
      zoneGuide: null,
      ratio,
      delta,
      headline: 'We need a few nights to find your usual',
      body: 'Resting HR only becomes a traffic light once there is a 7-day average. Keep syncing COROS — after a week this page can tell you whether last night was below usual, typical, or a rise.',
    }
  }

  const copy = {
    below: {
      headline: 'Quieter than your usual night',
      body: `${bpm(today)} vs a 7-day usual of ${bpm(usual7)} (${Number(ratio).toFixed(2)}×)${deltaLabel}. Useful after a hard block; do not treat it as a licence to pile on extra work.`,
    },
    typical: {
      headline: 'Right around your usual night',
      body: `${bpm(today)} vs ${bpm(usual7)} (${Number(ratio).toFixed(2)}×)${deltaLabel}. Train as planned if sleep and HRV agree.`,
    },
    high: {
      headline: 'A few beats above your recent nights',
      body: `${bpm(today)} against ${bpm(usual7)} (${Number(ratio).toFixed(2)}×)${deltaLabel}. Ease intensity until nights return toward typical.`,
    },
    elevated: {
      headline: 'Resting HR is up — this is a back-off night',
      body: `${bpm(today)} vs ${bpm(usual7)} (${ratio != null ? `${Number(ratio).toFixed(2)}×` : 'no usual yet'})${deltaLabel}. Cut quality. A rise of about 7 bpm is a coaching flag even if the week’s average is also high.`,
    },
  }

  const selected = copy[zone.id] || copy.typical
  return {
    zone,
    zoneGuide,
    ratio,
    delta,
    days: days || 0,
    usual28,
    headline: selected.headline,
    body: selected.body,
  }
}

export function summarizeRhrPoints(points) {
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
