export const SLEEP_FACTOR_GUIDES = {
  score: {
    title: 'Sleep score',
    summary:
      'COROS Sleep Score summarizes how restorative the night was using duration, stage balance, wakefulness, and schedule consistency.',
    sections: [
      {
        heading: 'What it means',
        body: 'Higher scores usually mean enough total sleep with healthy deep/REM balance and limited awakenings. Scores are personal — compare to your own recent nights.',
      },
      {
        heading: 'How COROS uses it',
        body: 'A full assessment is given for the first sleep longer than about 3 hours. Shorter sessions are logged as naps and usually do not receive a full score.',
      },
      {
        heading: 'How to use it',
        body: 'After low scores, keep intensity easy and protect the next night. Stack hard sessions after several solid nights.',
      },
    ],
  },
  duration: {
    title: 'Total sleep',
    summary:
      'Total sleep is main overnight sleep plus naps that contribute to the day. Most athletes recover best near 7–9 hours across 24 hours.',
    sections: [
      {
        heading: 'What it means',
        body: 'Duration is the strongest base layer of sleep quality. Consistently short nights raise injury and illness risk even if stage % looks fine.',
      },
      {
        heading: 'Naps',
        body: 'COROS counts naps toward total sleep. Naps under ~3 hours typically do not get stage breakdowns.',
      },
      {
        heading: 'Targets',
        body: 'Aim for a stable nightly window first. Add a short nap when overnight sleep is cut short by travel or early sessions.',
      },
    ],
  },
  deep: {
    title: 'Deep sleep',
    summary:
      'Deep sleep supports physical repair, immune function, and recovery from hard training. COROS often targets roughly 16–30% of total sleep.',
    sections: [
      {
        heading: 'What it means',
        body: 'Deep (slow-wave) sleep is when growth-hormone release and tissue repair are highest. Too little deep sleep often shows up as heavy legs and poor readiness.',
      },
      {
        heading: 'What moves it',
        body: 'Consistent bedtime, cooler room, lower evening alcohol, and well-timed hard sessions earlier in the day tend to protect deep sleep.',
      },
    ],
  },
  rem: {
    title: 'REM sleep',
    summary:
      'REM supports learning, mood, and skill consolidation. COROS typically expects roughly 11–35% of nightly sleep in REM.',
    sections: [
      {
        heading: 'What it means',
        body: 'REM usually increases in later cycles of the night. Cutting sleep short often steals REM first.',
      },
      {
        heading: 'How to use it',
        body: 'If REM is chronically low, prioritize a longer sleep opportunity and keep wake time consistent — especially before technical or high-skill sessions.',
      },
    ],
  },
  light: {
    title: 'Light sleep',
    summary:
      'Light sleep bridges deep and REM cycles. It is a normal majority of the night and still contributes to recovery.',
    sections: [
      {
        heading: 'What it means',
        body: 'Most nights include a large share of light sleep. Extremely high light % with low deep/REM can mean fragmented or shallow rest.',
      },
    ],
  },
  awake: {
    title: 'Awake time',
    summary:
      'Awake time includes remembered wake-ups and brief arousals. Under about 20 minutes overnight is generally considered good.',
    sections: [
      {
        heading: 'What it means',
        body: 'More wakefulness lowers sleep efficiency and usually pulls the sleep score down even when total time in bed looks long.',
      },
      {
        heading: 'How to use it',
        body: 'If awake time stays high, review caffeine timing, late screens, room temperature, and stress load before hard training blocks.',
      },
    ],
  },
  consistency: {
    title: 'Bedtime consistency',
    summary:
      'A steady bedtime keeps circadian rhythm aligned so recovery systems fire on schedule. COROS builds a baseline after about a week of tracking.',
    sections: [
      {
        heading: 'What we show',
        body: 'Advance Athlete Lab estimates consistency from stored bedtimes as average bedtime plus night-to-night variation (minutes). Lower variation = more consistent.',
      },
      {
        heading: 'How to use it',
        body: 'Pick a target bedtime window and protect it on easy days too. Weekend swings of 1–2 hours can blunt Monday readiness.',
      },
    ],
  },
  hrv: {
    title: 'Sleep HRV',
    summary:
      'Overnight HRV reflects autonomic recovery. Higher HRV relative to your baseline usually means better readiness.',
    sections: [
      {
        heading: 'What it means',
        body: 'HRV is highly individual. Trend and assessment text matter more than matching another athlete’s number.',
      },
      {
        heading: 'How to use it',
        body: 'Pair HRV with sleep score and how you feel. A multi-day downtrend with poor sleep is a stronger back-off signal than one noisy night.',
      },
    ],
  },
  sleepHr: {
    title: 'Average sleep HR',
    summary:
      'Average heart rate during the overnight sleep window. Lower overnight HR (for you) often tracks with better recovery.',
    sections: [
      {
        heading: 'What it means',
        body: 'Sleep HR is separate from all-day average HR. Heat, illness, alcohol, or incomplete recovery can elevate it.',
      },
      {
        heading: 'How to use it',
        body: 'Watch the 7-day average. A rising overnight HR with falling HRV often precedes a forced rest day.',
      },
    ],
  },
}
