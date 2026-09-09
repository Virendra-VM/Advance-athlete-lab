/**
 * Shared Health & Recovery visual system (Sleep-page base + per-metric chart colors).
 * Indigo accents / blue grid & hover; series colors vary by metric.
 */

export const HEALTH_CHART = {
  grid: 'color-mix(in srgb, var(--aal-line) 85%, transparent)',
  cursor: 'rgba(91, 141, 239, 0.08)',
  cursorStroke: '#5B8DEF',
  primary: '#5B8DEF',
  primarySoft: 'rgba(91, 141, 239, 0.18)',
  secondary: '#FB7185',
  secondarySoft: 'rgba(251, 113, 133, 0.14)',
  tooltipBg: 'var(--aal-card)',
  tooltipBorder: 'var(--aal-line)',
}

/** Metric-specific line colors (primary = main series, secondary = companion). */
export const HEALTH_METRIC_COLORS = {
  sleep: {
    primary: '#5B8DEF',
    primarySoft: 'rgba(91, 141, 239, 0.18)',
    secondary: '#14B8A6',
    secondarySoft: 'rgba(20, 184, 166, 0.16)',
    sleepHr: '#FB7185',
    sleepHrSoft: 'rgba(251, 113, 133, 0.14)',
  },
  recovery: {
    primary: '#6366F1',
    primarySoft: 'rgba(99, 102, 241, 0.18)',
    secondary: null,
  },
  hrv: {
    primary: '#14B8A6',
    primarySoft: 'rgba(20, 184, 166, 0.16)',
    secondary: null,
  },
  stress: {
    primary: '#F59E0B',
    primarySoft: 'rgba(245, 158, 11, 0.18)',
    secondary: null,
  },
  rhr: {
    primary: '#FB7185',
    primarySoft: 'rgba(251, 113, 133, 0.14)',
    secondary: null,
  },
  daily: {
    primary: '#5B8DEF',
    primarySoft: 'rgba(91, 141, 239, 0.18)',
    secondary: '#FB7185',
    secondarySoft: 'rgba(251, 113, 133, 0.14)',
  },
  steps: {
    primary: '#5B8DEF',
    primarySoft: 'rgba(91, 141, 239, 0.18)',
    secondary: '#FB7185',
  },
  calories: {
    primary: '#FB7185',
    primarySoft: 'rgba(251, 113, 133, 0.14)',
    secondary: null,
  },
  avg_hr: {
    primary: '#FB7185',
    primarySoft: 'rgba(251, 113, 133, 0.14)',
    secondary: null,
  },
  volume: {
    primary: '#5B8DEF',
    primarySoft: 'rgba(91, 141, 239, 0.18)',
    secondary: '#6366F1',
    secondarySoft: 'rgba(99, 102, 241, 0.18)',
    muted: '#94A3B8',
  },
  load: {
    primary: '#6366F1',
    primarySoft: 'rgba(99, 102, 241, 0.18)',
    secondary: '#5B8DEF',
    secondarySoft: 'rgba(91, 141, 239, 0.18)',
  },
}

export function healthColorsForMetric(metric) {
  return (
    HEALTH_METRIC_COLORS[metric] || {
      primary: HEALTH_CHART.primary,
      primarySoft: HEALTH_CHART.primarySoft,
      secondary: HEALTH_CHART.secondary,
      secondarySoft: HEALTH_CHART.secondarySoft,
    }
  )
}

/** Sleep chart aliases — same tokens as Sleep page, sourced from shared theme. */
export function sleepChartColors() {
  const sleep = healthColorsForMetric('sleep')
  const hrv = healthColorsForMetric('hrv')
  return {
    duration: sleep.primary,
    durationSoft: sleep.primarySoft,
    hrv: hrv.primary,
    hrvSoft: hrv.primarySoft,
    sleepHr: sleep.sleepHr,
    sleepHrSoft: sleep.sleepHrSoft,
    grid: HEALTH_CHART.grid,
    cursor: HEALTH_CHART.cursor,
    tooltipBg: HEALTH_CHART.tooltipBg,
    tooltipBorder: HEALTH_CHART.tooltipBorder,
  }
}
