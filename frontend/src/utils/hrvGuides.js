/** HRV vs your usual night. Scale is 0.70–1.30 of the 7-day mean (not ACWR bands). */

export const HRV_SCALE = { min: 0.7, max: 1.3 }

export const HRV_ZONES = [
  {
    id: 'suppressed',
    from: 0.7,
    to: 0.9,
    label: 'Suppressed',
    range: 'below 90% of usual',
    color: '#FB7185',
    meaning:
      'Last night’s HRV sat well below your recent average. The autonomic system often looks like this after hard training, poor sleep, illness, alcohol, or heat — it is a back-off flag, not a diagnosis.',
    workouts:
      'Easy aerobic only, or rest. Skip intervals, races, and strength maxes. Keep any session conversational.',
    improve:
      'Protect tonight: earlier bedtime, no late caffeine, cooler room. Repeat easy days until you are back near your usual night.',
  },
  {
    id: 'low',
    from: 0.9,
    to: 0.95,
    label: 'A little low',
    range: '90 – 95% of usual',
    color: '#F59E0B',
    meaning:
      'Slightly below your 7-day baseline. One night is often noise. Two or three in a row, especially with rising resting HR, is accumulated fatigue.',
    workouts:
      'Hold planned easy days. If quality is on the calendar, shorten it or make it fully aerobic. Do not add a new hard session.',
    improve:
      'Sleep and easy volume first. Check alcohol, late screens, and yesterday’s intensity before you blame the training plan.',
  },
  {
    id: 'typical',
    from: 0.95,
    to: 1.08,
    label: 'Typical',
    range: '95 – 108% of usual',
    color: '#14B8A6',
    meaning:
      'Close to your own recent nights. For HRV, “normal for you” is the useful zone — not matching another athlete’s milliseconds.',
    workouts:
      'Train as planned if sleep and how you feel agree. Quality can stay. Do not stack a new interval set just because HRV looks fine.',
    improve:
      'Keep the sleep window steady. HRV-guided training works best when you change one thing at a time after several typical nights.',
  },
  {
    id: 'high',
    from: 1.08,
    to: 1.3,
    label: 'Above usual',
    range: 'above 108% of usual',
    color: '#5B8DEF',
    meaning:
      'Higher than your recent average. Often a good recovery night. Sometimes it is a rebound after a hard block, or extra parasympathetic activity before you feel fully fresh — pair it with sleep and mood.',
    workouts:
      'Green light for planned quality if legs and sleep agree. Still avoid dumping a surprise long + hard day on the same date.',
    improve:
      'Use the window. Then return to typical nights rather than chasing a higher and higher number.',
  },
]

export const HRV_LEARN = [
  {
    id: 'what',
    title: 'What is HRV?',
    body: [
      'Heart-rate variability is the change in time between successive heartbeats (RR intervals), usually in milliseconds. A flexible, well-recovered nervous system tends to show more beat-to-beat variation — especially the parasympathetic (vagal) component captured by overnight rMSSD-style scores.',
      'A high number is not “fitter” in the way VO₂ is. Elite endurance athletes often have higher HRV, but your useful comparison is always you vs you. Age, sex, and recording method all shift the raw value.',
    ],
    refs: [
      {
        label: 'Shaffer F, Ginsberg JP. An overview of heart rate variability metrics (2017)',
        href: 'https://pmc.ncbi.nlm.nih.gov/articles/PMC5642338/',
        note: 'open access; time-domain metrics including rMSSD',
      },
      {
        label: 'Task Force. Heart rate variability standards (Circulation, 1996)',
        href: 'https://www.ahajournals.org/doi/10.1161/01.cir.93.5.1043',
        note: 'classic measurement standards',
      },
    ],
  },
  {
    id: 'sleep',
    title: 'Why overnight (sleep) HRV?',
    body: [
      'This page uses COROS sleep HRV — the average over the overnight window, not a 60-second morning spot check. Sleep recordings reduce movement noise and capture the night’s parasympathetic rebound after the day’s load.',
      'Morning orthostatic tests and sleep averages are related but not identical. Stay consistent: do not mix a watch-sleep number with a chest-strap sitting test and call the jump “fatigue.”',
    ],
    refs: [
      {
        label: 'Buchheit M. Monitoring training status with HRV (Front Physiol, 2014)',
        href: 'https://pmc.ncbi.nlm.nih.gov/articles/PMC4120687/',
        note: 'open access; why standardized recordings matter',
      },
    ],
  },
  {
    id: 'usual',
    title: 'What is “usual” HRV on this page?',
    body: [
      'Usual = the average of your last 7 nights with an HRV value. Last night ÷ that average is “vs usual.” 1.00 means you matched the week. 0.88 means about 12% below. 1.12 means about 12% above.',
      'Seven nights is long enough to smooth one noisy sleep, short enough to still move when a training block bites. A 28-day mean is shown on the chart as extra context; it is slower on purpose.',
    ],
    refs: [
      {
        label: 'Plews DJ et al. Training adaptation and HRV in elite endurance athletes (2013)',
        href: 'https://pubmed.ncbi.nlm.nih.gov/23852425/',
        note: 'rolling baselines vs isolated mornings',
      },
    ],
  },
  {
    id: 'zones',
    title: 'How to read the zones',
    body: [
      'The strip is not the ACWR 0.8–1.3 injury bands. Those are for training load. Here, bands sit around your own mean: below ~90% suppressed, 90–95% a little low, 95–108% typical, above that a high night.',
      'COROS also writes an assessment (often “balanced” or “unbalanced”). If they flag unbalanced, treat the night as suppressed even when the ratio is only slightly low — two lenses, same decision: ease intensity.',
    ],
    refs: [
      {
        label: 'Laborde S, Mosley E, Thayer JF. Heart rate variability and cardiac vagal tone (2017)',
        href: 'https://pmc.ncbi.nlm.nih.gov/articles/PMC5624990/',
        note: 'open access; vagal tone and measurement caveats',
      },
    ],
  },
  {
    id: 'why',
    title: 'Why it matters for workouts',
    body: [
      'HRV is one of the better non-invasive windows on cardiac autonomic recovery. Reviews in endurance sport link a falling HRV trend (not a single dip) with incomplete recovery and a higher chance that the next quality session lands poorly.',
      'Use it with sleep, resting HR, and how you feel. A low HRV night after a planned hard day can be normal. A low HRV night plus short sleep plus up-ticked resting HR is the classic “make tomorrow easy” pattern.',
    ],
    refs: [
      {
        label: 'Buchheit M. Monitoring training status with HRV (2014)',
        href: 'https://pmc.ncbi.nlm.nih.gov/articles/PMC4120687/',
      },
      {
        label: 'Plews DJ et al. HRV and training adaptation (Sports Med, 2013)',
        href: 'https://pubmed.ncbi.nlm.nih.gov/23852425/',
      },
    ],
  },
  {
    id: 'calc',
    title: 'How this page calculates it',
    body: [
      'Last night = the newest COROS sleep HRV in milliseconds. 7-day usual = mean of up to the last 7 nights that have a value. Vs usual = last night ÷ 7-day mean (blank until a usual night exists). Duplicate calendar days are not double-counted.',
      'The chart is the nightly series. The dashed line is that 7-day mean. Explore history pulls a wider COROS window when the cache is thin.',
    ],
    refs: [
      {
        label: 'Shaffer & Ginsberg. HRV metrics overview (2017)',
        href: 'https://pmc.ncbi.nlm.nih.gov/articles/PMC5642338/',
        note: 'what the millisecond number is actually measuring',
      },
    ],
  },
  {
    id: 'limits',
    title: 'What it cannot tell you',
    body: [
      'HRV is noisy. Breathing, alcohol, illness, altitude, late food, and a bad electrode night all move it. It does not measure muscle damage, tendon load, or mood by itself. A “typical” HRV with a niggle is still a niggle.',
      'Do not chase a higher number with extra easy kilometres. Do not treat one green night as a licence for a smash session if the week’s training load already spiked. Pair this page with Sleep and Training Load.',
    ],
    refs: [
      {
        label: 'Laborde et al. HRV guidelines and caveats (2017)',
        href: 'https://pmc.ncbi.nlm.nih.gov/articles/PMC5624990/',
      },
    ],
  },
]

function mean(values) {
  const list = values.filter((value) => value != null && !Number.isNaN(Number(value)))
  if (!list.length) return null
  return list.reduce((sum, value) => sum + Number(value), 0) / list.length
}

export function hrvRatio(lastNight, usual) {
  if (lastNight == null || usual == null || Number(usual) <= 0) return null
  return Number(lastNight) / Number(usual)
}

export function hrvMarkerPercent(ratio) {
  if (ratio == null || Number.isNaN(Number(ratio))) return null
  const { min, max } = HRV_SCALE
  return Math.min(100, Math.max(0, ((Number(ratio) - min) / (max - min)) * 100))
}

export function getHrvZone(ratio, assessment = '') {
  const text = String(assessment || '').toLowerCase()
  const unbalanced = /\bunbalanced\b|\blow\b|\bpoor\b|\bsuppressed\b/.test(text)
  if (ratio == null || Number.isNaN(Number(ratio))) {
    if (unbalanced) return HRV_ZONES[0]
    return {
      id: 'empty',
      label: 'Need more nights',
      color: '#94a3b8',
    }
  }
  const value = Number(ratio)
  if (unbalanced && value < 1.08) return HRV_ZONES[0]
  if (value < 0.9) return HRV_ZONES[0]
  if (value < 0.95) return HRV_ZONES[1]
  if (value < 1.08) return HRV_ZONES[2]
  return HRV_ZONES[3]
}

export function interpretHrv({ lastNight, usual7, usual28, assessment, nights }) {
  const ratio = hrvRatio(lastNight, usual7)
  const zone = getHrvZone(ratio, assessment)
  const zoneGuide = HRV_ZONES.find((item) => item.id === zone.id) || null
  const ms = (value) => (value == null ? '—' : `${Math.round(Number(value))} ms`)

  if (zone.id === 'empty') {
    return {
      zone,
      zoneGuide: null,
      ratio,
      headline: 'We need a few nights to find your usual',
      body: 'HRV only becomes a traffic light once there is a 7-day average. Keep sleeping with the watch on — after a week this page can tell you whether last night was quiet, typical, or a dip.',
    }
  }

  const copy = {
    suppressed: {
      headline: 'Last night sat well below your usual',
      body: `${ms(lastNight)} vs a 7-day usual of ${ms(usual7)} (${Number(ratio).toFixed(2)}×). Ease intensity until nights return toward typical.`,
    },
    low: {
      headline: 'A little below your recent nights',
      body: `${ms(lastNight)} against ${ms(usual7)} usual (${Number(ratio).toFixed(2)}×). One night is often noise; a short streak plus poor sleep is a stronger easy-day cue.`,
    },
    typical: {
      headline: 'Right around your usual night',
      body: `${ms(lastNight)} vs ${ms(usual7)} (${Number(ratio).toFixed(2)}×). That is the useful zone — train as planned if sleep and legs agree.`,
    },
    high: {
      headline: 'Above your recent average',
      body: `${ms(lastNight)} vs ${ms(usual7)} (${Number(ratio).toFixed(2)}×). Often a recovered night. Still match it to how you feel before you add extra quality.`,
    },
  }

  const selected = copy[zone.id] || copy.typical
  return {
    zone,
    zoneGuide,
    ratio,
    nights: nights || 0,
    usual28,
    headline: selected.headline,
    body: selected.body,
  }
}

export function summarizeHrvPoints(points) {
  const valued = (points || [])
    .filter((point) => point.value != null && point.date)
    .sort((a, b) => String(a.date).localeCompare(String(b.date)))
  const last = valued.length ? valued[valued.length - 1] : null
  const last7 = valued.slice(-7).map((point) => Number(point.value))
  const last28 = valued.slice(-28).map((point) => Number(point.value))
  return {
    lastNight: last?.value ?? null,
    lastDate: last?.date ?? null,
    assessment: last?.label || last?.meta?.hrv_assessment || '',
    usual7: mean(last7),
    usual28: mean(last28),
    nights: valued.length,
    valued,
  }
}
