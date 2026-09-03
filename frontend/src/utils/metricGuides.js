export const METRIC_GUIDES = {
  recovery: {
    title: 'Recovery',
    summary:
      'Recovery estimates how ready your body is for training today, based on recent load and overnight signals.',
    sections: [
      {
        heading: 'What it means',
        body: 'A higher recovery percentage means more capacity for hard work. Lower recovery suggests prioritizing easy sessions or rest so fatigue can clear.',
      },
      {
        heading: 'How COROS uses it',
        body: 'COROS combines recent training stress with recovery status to recommend intensity. Full recovery does not mean you must train hard — it means your system can absorb more load.',
      },
      {
        heading: 'How to use it',
        body: 'Match workout intensity to recovery. Heavy intervals on low recovery raise injury and overreaching risk. Easy aerobic work is usually fine even when recovery is moderate.',
      },
      {
        heading: 'History note',
        body: 'COROS MCP returns the live recovery snapshot (not a full multi-month recovery calendar). Advance Athlete Lab stores one snapshot per day when you sync, so the chart grows over time.',
      },
    ],
  },
  sleep: {
    title: 'Sleep',
    summary:
      'Sleep score summarizes overnight duration and stage balance — the foundation of recovery and adaptation. Open each factor on the Sleep page for trends and detail.',
    sections: [
      {
        heading: 'What it means',
        body: 'Sleep score reflects how restorative the night was. Duration, deep sleep, REM, awakenings, and bedtime consistency all influence the score.',
      },
      {
        heading: 'Why it matters',
        body: 'Most fitness gains consolidate during sleep. Poor nights often show up as higher stress, lower HRV, and reduced readiness the next day.',
      },
      {
        heading: 'How to use it',
        body: 'After low sleep scores, prefer easy volume or technique work. Stack hard sessions after consistent high-quality sleep.',
      },
      {
        heading: 'Data note',
        body: 'Stage mix, awake time, HRV, and sleep HR come from COROS MCP. Bedtime/wake and naps appear after sync when COROS includes them in the sleep report.',
      },
    ],
  },
  hrv: {
    title: 'HRV',
    summary:
      'Heart-rate variability reflects autonomic balance. Higher HRV (for you) usually signals better recovery readiness.',
    sections: [
      {
        heading: 'What it means',
        body: 'HRV measures variation between heartbeats. It is highly individual — compare to your own baseline, not someone else’s numbers.',
      },
      {
        heading: 'Why it matters',
        body: 'Rising HRV with stable sleep often means your nervous system is coping well. Sudden drops with heavy training can flag accumulated fatigue.',
      },
      {
        heading: 'How to use it',
        body: 'Use HRV with sleep, RHR, and how you feel. One low day is noise; a multi-day downtrend is a stronger signal to back off.',
      },
    ],
  },
  stress: {
    title: 'Stress',
    summary:
      'Daily stress averages how hard your body was working outside structured workouts — life load plus recovery debt.',
    sections: [
      {
        heading: 'What it means',
        body: 'Stress combines physiological load from training, work, travel, illness, and poor sleep into a daily average.',
      },
      {
        heading: 'Why it matters',
        body: 'High all-day stress can blunt recovery even if training volume looks moderate. It helps explain “tired for no reason” days.',
      },
      {
        heading: 'How to use it',
        body: 'If stress stays elevated, cut intensity first, protect sleep, and keep easy aerobic work conversational.',
      },
    ],
  },
  rhr: {
    title: 'Resting HR',
    summary:
      'Resting heart rate is a simple recovery marker. A rise above your baseline often means incomplete recovery or illness.',
    sections: [
      {
        heading: 'What it means',
        body: 'RHR is typically measured during sleep or first thing in the morning. Fitter athletes often have lower baselines.',
      },
      {
        heading: 'Why it matters',
        body: 'Elevated RHR with low HRV and poor sleep is a classic overreaching pattern. Isolated spikes can also follow alcohol, heat, or late meals.',
      },
      {
        heading: 'How to use it',
        body: 'Track trends, not single nights. A multi-day rise is a cue for easier training until RHR returns toward baseline.',
      },
    ],
  },
  daily: {
    title: 'Daily Health',
    summary:
      'Steps and calories show everyday movement outside workouts — useful context for total load and recovery.',
    sections: [
      {
        heading: 'What it means',
        body: 'Daily health captures non-workout activity: walking, standing, and incidental movement that still costs energy.',
      },
      {
        heading: 'Why it matters',
        body: 'High step days plus hard workouts can tip you into fatigue. Very low movement can also leave you feeling flat.',
      },
      {
        heading: 'How to use it',
        body: 'On hard training days, keep incidental load reasonable. On recovery days, easy walking often helps without adding much stress.',
      },
    ],
  },
  avg_hr: {
    title: 'Average HR',
    summary:
      'Average heart rate across the day reflects overall cardiovascular demand from training and daily life.',
    sections: [
      {
        heading: 'What it means',
        body: 'Day-average HR rises with workouts, heat, stress, and caffeine, and falls with rest and strong aerobic fitness.',
      },
      {
        heading: 'How to use it',
        body: 'Use it as context beside RHR and training load. Large jumps without planned hard sessions deserve a closer look at sleep and stress.',
      },
    ],
  },
  acwr: {
    title: 'Volume & ACWR',
    summary:
      'Volume is distance. ACWR is this week’s kilometres divided by your usual week — a traffic light for whether you jumped too fast.',
    sections: [
      {
        heading: 'What it means',
        body: 'Acute load is the last 7 days. Chronic load is the last 28 days divided by 4 (a usual week). Their ratio near 0.8–1.3 is the typical productive zone; above 1.5 is a spike.',
      },
      {
        heading: 'How to use it',
        body: 'Progress one thing at a time (distance or intensity). After a spike, hold or deload so the 28-day average can catch up. Pair with sleep and how joints feel.',
      },
      {
        heading: 'Data note',
        body: 'This is GPS distance from synced activities, not COROS effort load. Indoor, swim, and strength sessions may look small if kilometres are low.',
      },
    ],
  },
  load: {
    title: 'Training Load',
    summary:
      'Training load is COROS effort — short-term stress versus your long-term fitness base. The ratio uses the same traffic-light bands as distance ACWR (about 0.8–1.3 productive, above 1.5 a spike).',
    sections: [
      {
        heading: 'What it means',
        body: 'Short-term load reflects recent days of training. Long-term load reflects fitness built over weeks. Their ratio shows whether you are ramping, maintaining, or overreaching.',
      },
      {
        heading: 'Why it matters',
        body: 'A rising ratio with strong recovery can support fitness gains. A high ratio with poor sleep/HRV is a warning to ease off.',
      },
      {
        heading: 'History note',
        body: 'COROS provides about a week of daily load comments per sync. Sync regularly so the chart keeps extending.',
      },
    ],
  },
  vo2max: {
    title: 'Fitness',
    summary:
      'VO2max and related fitness markers estimate aerobic capacity and race potential from COROS EvoLab.',
    sections: [
      {
        heading: 'What it means',
        body: 'VO2max is an estimate of maximal oxygen uptake. Threshold pace and race predictions translate that fitness into usable training targets.',
      },
      {
        heading: 'Why it matters',
        body: 'Fitness changes slowly. Watch weeks-to-months trends rather than day-to-day noise.',
      },
      {
        heading: 'History note',
        body: 'COROS MCP returns the current fitness snapshot. We store one value per day when you sync so long-term trends appear over time.',
      },
    ],
  },
  fitness: {
    title: 'Fitness',
    summary:
      'VO2max and related fitness markers estimate aerobic capacity and race potential from COROS EvoLab.',
    sections: [
      {
        heading: 'What it means',
        body: 'VO2max is an estimate of maximal oxygen uptake. Threshold pace and race predictions translate that fitness into usable training targets.',
      },
      {
        heading: 'History note',
        body: 'COROS MCP returns the current fitness snapshot. We store one value per day when you sync so long-term trends appear over time.',
      },
    ],
  },
}

export function guideForMetric(metric) {
  return METRIC_GUIDES[metric] || METRIC_GUIDES[metric === 'training_load' ? 'load' : metric] || null
}
