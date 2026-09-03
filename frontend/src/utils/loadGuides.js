import { getAcwrZone } from './statusColors'

/** Zone widths on a 0–2.0 scale so the strip matches the gauge. */
export const ACWR_ZONES = [
  {
    id: 'recovery',
    from: 0,
    to: 0.8,
    label: 'Underloaded',
    range: 'below 0.8',
    colorClass: 'bg-recovery',
    meaning: 'This week is quieter than your body is used to. Recovery happens here — fitness does not.',
    workouts:
      'Easy aerobic sessions, technique, mobility. Skip the “make-up” long day that dumps a month of km into one weekend.',
    improve:
      'Rebuild over 2–3 weeks. Add a little distance to easy days first. Keep hard sessions the same until the ratio is back near 1.0.',
  },
  {
    id: 'sweet',
    from: 0.8,
    to: 1.3,
    label: 'Sweet spot',
    range: '0.8 – 1.3',
    colorClass: 'bg-sage',
    meaning:
      'Last 7 days are close to your usual month. This is where most athletes adapt: enough stimulus, not a shock.',
    workouts:
      'Keep planned quality. Nudge easy volume a little if you feel good. Do not stack a new interval set and a longer long run in the same week.',
    improve:
      'Progress one thing at a time — distance or intensity, not both. A small weekly step-up lets chronic load catch up so the ratio stays here.',
  },
  {
    id: 'caution',
    from: 1.3,
    to: 1.5,
    label: 'Caution',
    range: '1.3 – 1.5',
    colorClass: 'bg-amber-status',
    meaning:
      'You jumped ahead of what the last month prepared you for. Tissue and tendons lag behind fitness — this is where niggles start.',
    workouts:
      'Hold intensity where it is. Do not add a new workout type. Sleep and easy days matter more than extra km.',
    improve:
      'Repeat a similar week, or trim 10–15% off the longest session. Let the 28-day average rise before you push again.',
  },
  {
    id: 'high',
    from: 1.5,
    to: 2,
    label: 'High risk',
    range: 'above 1.5',
    colorClass: 'bg-danger-muted',
    meaning:
      'Acute load has spiked versus your recent average. Several studies link this zone to higher injury rates — it is a warning, not a diagnosis.',
    workouts:
      'Cut intensity first. Keep a short easy session if you need to move. Protect the next quality day rather than chasing this week’s plan.',
    improve:
      'Take 7–10 easier days so chronic load can absorb the spike. Then rebuild. One deload is cheaper than three weeks off injured.',
  },
]

export const LOAD_LEARN = [
  {
    id: 'volume',
    title: 'What is volume?',
    body: [
      'In sports science, volume is external load — how much work you did in the world, not how hard it felt. This page uses total distance from synced activities as that size-of-the-week number.',
      'Distance is only one external-load lens. A 60-minute easy run and a 60-minute interval session can share similar kilometres and very different internal stress (heart rate, hormones, muscle damage). That is why Volume and Training Load can disagree.',
    ],
    refs: [
      {
        label: 'Halson SL. Monitoring training load to understand fatigue in athletes (2014)',
        href: 'https://pmc.ncbi.nlm.nih.gov/articles/PMC4213373/',
        note: 'internal vs external load, open access',
      },
    ],
  },
  {
    id: 'acute',
    title: 'What is acute load?',
    body: [
      'Acute load is recent work. Here it is the last 7 days of distance — the answer to “what did I just do?”',
      'It moves quickly. One long weekend, a camp, or two stacked quality days can lift it a lot, even if your month still looks ordinary. That short window is why a spike shows up here before it shows up in the usual-week number.',
    ],
    refs: [
      {
        label: 'Gabbett TJ. The training–injury prevention paradox (BJSM, 2016)',
        href: 'https://pmc.ncbi.nlm.nih.gov/articles/PMC4789704/',
        note: 'acute vs chronic load, open access PDF',
      },
    ],
  },
  {
    id: 'chronic',
    title: 'What is chronic load?',
    body: [
      'Chronic load is what your body is used to. Here it is the last 28 days of distance, divided by 4, so you can compare “this week” with “a usual week.”',
      'It changes slowly. That is why the same 80 km feels harder after two easy weeks than in the middle of a build — tissue capacity (bone, tendon, muscle) trails fitness. A high chronic load, built gradually, is often protective; a sudden jump onto a thin base is not.',
    ],
    refs: [
      {
        label: 'Soligard T et al. IOC consensus: load in sport and risk of injury (BJSM, 2016)',
        href: 'https://bjsm.bmj.com/content/50/17/1030',
        note: 'rapid load changes vs progressive high load',
      },
    ],
  },
  {
    id: 'acwr',
    title: 'What is ACWR?',
    body: [
      'Acute:Chronic Workload Ratio = this week ÷ your usual week. 1.0 means you matched your average. 1.2 is about 20% more. 0.7 is a quieter recovery week.',
      'Across many sports, reviews often find the lowest injury signal around 0.8–1.3, with more problems when the ratio sits high (often ≥1.5). Those bands are a traffic light for how fast load is changing — not a VO₂ score, not a diagnosis, and not a promise that a “green” week cannot still hurt if the sessions were brutal.',
    ],
    refs: [
      {
        label: 'Maupin D et al. ACWR and injury risk: systematic review (2020)',
        href: 'https://pmc.ncbi.nlm.nih.gov/articles/PMC7047972/',
        note: 'trend for 0.80–1.30; open access',
      },
      {
        label: 'Gabbett TJ. Training–injury prevention paradox (2016)',
        href: 'https://pmc.ncbi.nlm.nih.gov/articles/PMC4789704/',
        note: 'classic 0.8–1.3 “sweet spot” figure',
      },
    ],
  },
  {
    id: 'why',
    title: 'Why it matters for workouts',
    body: [
      'Fitness (heart, lungs, running economy) can jump in days. Bone, tendon, and muscle remodel on slower clocks. A high ACWR is one simple flag that recent work outran that slower clock.',
      'The paradox in the research: well-prepared athletes who train hard with a high chronic load often get fewer injuries than undertrained athletes. The danger is usually the jump, not the work itself. Sleep, HRV, shoes, terrain, and how joints feel still sit beside the ratio.',
    ],
    refs: [
      {
        label: 'Gabbett TJ. Training–injury prevention paradox (BJSM, 2016)',
        href: 'https://pmc.ncbi.nlm.nih.gov/articles/PMC4789704/',
        note: 'high chronic load can protect; spikes often do not',
      },
      {
        label: 'IOC consensus on load and injury (2016)',
        href: 'https://bjsm.bmj.com/content/50/17/1030.full.pdf',
        note: 'PDF of the Soligard statement',
      },
    ],
  },
  {
    id: 'calc',
    title: 'How this page calculates it',
    body: [
      'Acute = sum of activity distance over the last 7 days. Chronic = last 28 days of distance ÷ 4. ACWR = acute ÷ chronic (blank if chronic is 0). Duplicate activities are ignored.',
      'This is a coupled rolling ratio: the last 7 days also sit inside the 28-day total, which is the method used in much of the early ACWR literature. It is distance, not heart-rate TRIMP. Indoor rides, swimming, and strength can look small if GPS kilometres are low.',
    ],
    refs: [
      {
        label: 'Maupin D et al. How studies calculate ACWR (2020 review)',
        href: 'https://pmc.ncbi.nlm.nih.gov/articles/PMC7047972/',
        note: '7:28 day windows are common; methods vary',
      },
    ],
  },
  {
    id: 'limits',
    title: 'What it cannot tell you',
    body: [
      'A ratio can mislead. A tiny usual week makes a normal week look “risky.” A huge base can hide a nasty intensity spike (downhill, intervals, new shoes) that barely moves kilometres. Researchers have also shown statistical quirks in ratio math — coupling, arbitrary cut-points — so ACWR is a question (“did I jump?”), not a causal injury model.',
      'Use it next to how you feel, sleep, and the Training Load page (effort). It is not medical advice.',
    ],
    refs: [
      {
        label: 'Impellizzeri FM et al. Training load and injury: conceptual pitfalls (2020)',
        href: 'https://pmc.ncbi.nlm.nih.gov/articles/PMC7534938/',
        note: 'why a ratio is a coarse flag, not a diagnosis',
      },
      {
        label: 'Frontiers editorial: is there scientific evidence for ACWR? (2021)',
        href: 'https://pmc.ncbi.nlm.nih.gov/articles/PMC8138569/',
        note: 'open-access summary of the debate',
      },
    ],
  },
]

function fmtKm(value) {
  return `${Number(value || 0).toFixed(1)} km`
}

function deltaLabel(acuteKm, chronicKm) {
  if (!chronicKm) return null
  const pct = Math.round((acuteKm / chronicKm - 1) * 100)
  if (pct === 0) return 'about the same as'
  if (pct > 0) return `${pct}% above`
  return `${Math.abs(pct)}% below`
}

export function interpretLoad({ acwr, acuteKm, chronicKm }) {
  const zone = getAcwrZone(acwr)
  const acute = Number(acuteKm || 0)
  const chronic = Number(chronicKm || 0)
  const delta = deltaLabel(acute, chronic)
  const zoneGuide = ACWR_ZONES.find((item) => item.id === zone.id) || null

  if (zone.id === 'empty' || chronic <= 0) {
    return {
      zone,
      zoneGuide: null,
      headline: 'We need a usual week to compare',
      body: 'ACWR only appears once there is a 28-day average. Keep syncing activities — after a few weeks this page can tell you whether you are ramping, recovering, or spiking.',
      actions: [
        'Sync Strava or COROS so distance lands in one place',
        'Train as planned; the first month builds your chronic baseline',
        'Until then, change only one variable per week (distance or intensity)',
      ],
      delta,
    }
  }

  const copy = {
    recovery: {
      headline: 'This week is lighter than your body is used to',
      body: `You covered ${fmtKm(acute)} in 7 days. A usual week for you is ${fmtKm(chronic)} — ${delta} your recent average. Good after a hard block; fitness stalls if every week stays this quiet.`,
    },
    sweet: {
      headline: 'You are building at a useful pace',
      body: `Last 7 days: ${fmtKm(acute)}. Usual week: ${fmtKm(chronic)} (${delta} average). That is the productive zone — enough work to adapt, not a shock to tendons and bone.`,
    },
    caution: {
      headline: 'This week jumped ahead of your usual',
      body: `You did ${fmtKm(acute)} in 7 days versus a usual ${fmtKm(chronic)} (${delta} average). Tissue lags fitness here. Hold the line rather than adding more.`,
    },
    high: {
      headline: 'Load spiked — this is the danger jump',
      body: `${fmtKm(acute)} in 7 days against a usual ${fmtKm(chronic)} (${delta} average). That spike is a classic injury-risk pattern. Back off intensity and let the month catch up.`,
    },
  }

  const selected = copy[zone.id] || copy.sweet
  return {
    zone,
    zoneGuide,
    headline: selected.headline,
    body: selected.body,
    actions: zoneGuide
      ? [zoneGuide.workouts, zoneGuide.improve]
      : [],
    delta,
  }
}

export function acwrMarkerPercent(acwr) {
  if (acwr == null || Number.isNaN(Number(acwr))) return null
  return Math.min(100, Math.max(0, (Number(acwr) / 2) * 100))
}

export function hasLoadHistory(stats) {
  const acute = Number(stats?.acute_load_km || 0)
  const chronic = Number(stats?.chronic_load_km || 0)
  const volume = (stats?.weekly_volume_history || []).some(
    (bucket) => Number(bucket.total_distance_km || 0) > 0,
  )
  return acute > 0 || chronic > 0 || volume
}

export function weeksWithDistance(stats) {
  return (stats?.weekly_volume_history || []).filter(
    (bucket) => Number(bucket.total_distance_km || 0) > 0,
  ).length
}

export function isSparseBaseline(stats) {
  return weeksWithDistance(stats) < 3
}

/** Same 0.8 / 1.3 / 1.5 bands as ACWR, written for COROS effort load. */
export const EFFORT_ZONES = [
  {
    id: 'recovery',
    from: 0,
    to: 0.8,
    label: 'Underloaded',
    range: 'below 0.8',
    colorClass: 'bg-recovery',
    meaning:
      'Recent effort is quieter than your fitness base. Good for absorption after a hard block; fitness stalls if every week stays here.',
    workouts:
      'Easy aerobic work and technique. Do not “make up” the week with a monster interval day.',
    improve:
      'Rebuild over 2–3 weeks. Add a little duration to easy sessions first. Keep quality the same until the ratio is back near 1.0.',
  },
  {
    id: 'sweet',
    from: 0.8,
    to: 1.3,
    label: 'Sweet spot',
    range: '0.8 – 1.3',
    colorClass: 'bg-sage',
    meaning:
      'Short-term load is close to long-term load. This is where most athletes adapt: enough stress, not a shock.',
    workouts:
      'Keep planned quality. Nudge easy volume a little if recovery looks good. Do not add a new hard session and extra duration in the same week.',
    improve:
      'Progress one thing at a time — duration or intensity. Small steps let long-term load catch up so the ratio stays here.',
  },
  {
    id: 'caution',
    from: 1.3,
    to: 1.5,
    label: 'Caution',
    range: '1.3 – 1.5',
    colorClass: 'bg-amber-status',
    meaning:
      'Recent effort jumped ahead of the fitness COROS has stored. Tissue still lags — this is where niggles start.',
    workouts:
      'Hold intensity. Do not add a new workout type. Sleep and easy days matter more than extra load points.',
    improve:
      'Repeat a similar week, or shorten the hardest session. Let long-term load rise before you push again.',
  },
  {
    id: 'high',
    from: 1.5,
    to: 2,
    label: 'High risk',
    range: 'above 1.5',
    colorClass: 'bg-danger-muted',
    meaning:
      'Short-term load has spiked versus your base. COROS and our safety rules treat this as a warning to back off — not a diagnosis.',
    workouts:
      'Cut intensity first. Keep a short easy session if you need to move. Protect the next quality day rather than chasing this week’s plan.',
    improve:
      'Take 7–10 easier days so long-term load can absorb the spike, then rebuild. One deload is cheaper than three weeks off injured.',
  },
]

export const EFFORT_LEARN = [
  {
    id: 'what',
    title: 'What is training load?',
    body: [
      'Here, training load is internal load: how much physiological work the session asked of you. COROS scores each workout with TRIMP — training impulse from intensity (mainly heart rate, or power when a meter is connected) × duration. Longer and harder both raise the score.',
      'That is why a brutal indoor ride can look loud here with almost no GPS kilometres, and why an easy long jog can look modest here even when Volume & ACWR shows a big week.',
    ],
    refs: [
      {
        label: 'COROS: Training Load — your metric for success',
        href: 'https://support.coros.com/hc/en-us/articles/16237531802772-Training-Load-Your-Metric-for-Success',
        note: 'how COROS defines session load',
      },
      {
        label: 'Halson SL. Monitoring training load (2014)',
        href: 'https://pmc.ncbi.nlm.nih.gov/articles/PMC4213373/',
        note: 'TRIMP and internal load, open access',
      },
    ],
  },
  {
    id: 'short',
    title: 'What is short-term load?',
    body: [
      'Short-term load is recent effort. On COROS this is Load Impact: about the last 7 days of training load, with more weight on the newest days (an exponentially weighted average).',
      'It moves quickly. A camp, a race, or two stacked interval days lifts it fast. Think of it as “how much stress did I just dump on the system?”',
    ],
    refs: [
      {
        label: 'COROS: how to interpret Training Status',
        href: 'https://coros.com/stories/coros-metrics/c/prepare-for-your-next-race-with-training-status',
        note: 'Load Impact ≈ 7-day rolling effort',
      },
      {
        label: 'COROS EvoLab help: Base Fitness, Load Impact, Intensity Trend',
        href: 'https://support.coros.com/hc/en-us/articles/4412789816724-EvoLab',
      },
    ],
  },
  {
    id: 'long',
    title: 'What is long-term load?',
    body: [
      'Long-term load is your fitness base. COROS calls it Base Fitness: about 42 days of training load, also exponentially weighted, so last month still matters but last week matters more.',
      'It changes slowly. That is why a sudden hard week feels worse than the same work mid-block — the base has not caught up. Built gradually, a higher base is what lets you absorb quality. Sit quiet for weeks and it declines.',
    ],
    refs: [
      {
        label: 'COROS Training Status: Base Fitness (42-day)',
        href: 'https://coros.com/stories/coros-metrics/c/prepare-for-your-next-race-with-training-status',
      },
      {
        label: 'IOC consensus on load in sport (2016)',
        href: 'https://bjsm.bmj.com/content/50/17/1030',
        note: 'progressive load vs rapid spikes',
      },
    ],
  },
  {
    id: 'ratio',
    title: 'What is the load ratio?',
    body: [
      'Load ratio = short-term ÷ long-term (COROS Intensity Trend = Load Impact ÷ Base Fitness). 1.0 means recent effort matches your base. 1.2 is about 20% more than you are used to. Below 0.8 is a quieter stretch.',
      'This page uses the same traffic-light bands as Volume & ACWR (about 0.8–1.3 productive, 1.3–1.5 caution, above 1.5 a spike). That lines up with COROS calling ≥1.5 (150%) Excessive. COROS’s “Optimized” band is a little wider (about 1.0–1.49); we keep 1.3 as caution because tissue still lags when recent effort jumps that far.',
    ],
    refs: [
      {
        label: 'COROS Intensity Trend = Load Impact ÷ Base Fitness',
        href: 'https://support.coros.com/hc/en-us/articles/4412789816724-EvoLab',
      },
      {
        label: 'Maupin D et al. ACWR bands in the literature (2020)',
        href: 'https://pmc.ncbi.nlm.nih.gov/articles/PMC7047972/',
        note: 'why 0.8–1.3 and ≥1.5 show up on this gauge too',
      },
    ],
  },
  {
    id: 'vs',
    title: 'How is this different from Volume & ACWR?',
    body: [
      'Volume & ACWR is external load (kilometres). This page is internal load (COROS TRIMP). Same athlete, same week, two questions: “how far?” vs “how hard on the engine?”',
      'They split on purpose. Lots of easy kilometres with a low heart rate looks big on Volume and quiet here. A VO₂ indoor session looks small on Volume and loud here. When they disagree, believe both: the musculoskeletal system felt the km; the cardiovascular system felt the effort.',
    ],
    refs: [
      {
        label: 'Halson SL. Internal vs external load (2014)',
        href: 'https://pmc.ncbi.nlm.nih.gov/articles/PMC4213373/',
      },
      {
        label: 'Bourdon PC et al. Monitoring athlete training loads: consensus (2017)',
        href: 'https://journals.humankinetics.com/view/journals/ijspp/12/s2/article-pS2-161.xml',
        note: 'why both lenses belong in a monitoring system',
      },
    ],
  },
  {
    id: 'comments',
    title: 'What are daily comments?',
    body: [
      'COROS writes a short coach note for each recent day (about a week per sync). Those notes are their reading of the ratio in plain language — useful colour around the numbers, not a second formula.',
      'Sync often so the chart and comments keep extending. A high ratio on two days of history is a hint, not a verdict.',
    ],
    refs: [
      {
        label: 'COROS EvoLab (Training Status and load comments)',
        href: 'https://support.coros.com/hc/en-us/articles/4412789816724-EvoLab',
      },
    ],
  },
  {
    id: 'limits',
    title: 'What it cannot tell you',
    body: [
      'TRIMP does not feel downhill eccentric load, new shoes, or a niggle. A thin fitness base makes a normal week look “risky.” A huge base can hide nasty mechanical stress that barely moves heart rate. Sleep, HRV, and how joints feel still sit beside the number.',
      'Same caution as ACWR: a ratio is a traffic light, not a fitness score and not medical advice. Researchers have warned against treating any load ratio as a proven cause of injury.',
    ],
    refs: [
      {
        label: 'Impellizzeri FM et al. Training-load injury research: pitfalls (2020)',
        href: 'https://pmc.ncbi.nlm.nih.gov/articles/PMC7534938/',
        note: 'open-access commentary',
      },
    ],
  },
]

export function interpretEffortLoad({ ratio, shortLoad, longLoad }) {
  const zone = getAcwrZone(ratio)
  const zoneGuide = EFFORT_ZONES.find((item) => item.id === zone.id) || null
  const short = shortLoad == null ? '—' : Math.round(Number(shortLoad))
  const long = longLoad == null ? '—' : Math.round(Number(longLoad))

  if (zone.id === 'empty' || ratio == null) {
    return {
      zone,
      zoneGuide: null,
      headline: 'Connect COROS to see effort load',
      body: 'Short and long-term load come from a COROS sync. Until then this page cannot tell you whether recent effort is ramping, recovering, or spiking.',
    }
  }

  const copy = {
    recovery: {
      headline: 'Recent effort is lighter than your base',
      body: `Short-term load is ${short} against a long-term base of ${long} (ratio ${Number(ratio).toFixed(2)}). Useful after a hard block; fitness stalls if every week stays this quiet.`,
    },
    sweet: {
      headline: 'You are loading at a useful pace',
      body: `Short-term ${short} vs long-term ${long} (ratio ${Number(ratio).toFixed(2)}). That is the productive zone — enough stress to adapt, not a shock.`,
    },
    caution: {
      headline: 'Recent effort jumped ahead of your base',
      body: `Short-term ${short} vs long-term ${long} (ratio ${Number(ratio).toFixed(2)}). Hold quality and let the base catch up rather than adding more.`,
    },
    high: {
      headline: 'Effort spiked — this is the danger jump',
      body: `Short-term ${short} against a base of ${long} (ratio ${Number(ratio).toFixed(2)}). Back off intensity and let long-term load absorb the week.`,
    },
  }

  const selected = copy[zone.id] || copy.sweet
  return {
    zone,
    zoneGuide,
    headline: selected.headline,
    body: selected.body,
  }
}
