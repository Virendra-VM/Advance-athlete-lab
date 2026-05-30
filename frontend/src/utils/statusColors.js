export const cardShellClass =
  'rounded-2xl border border-slate-100 bg-white shadow-sm dark:border-white/10 dark:bg-gray-800'

export const pageShellClass =
  'min-h-screen w-full bg-[#f8f7f4] text-slate-900 dark:bg-gray-900 dark:text-slate-100'

export const pagePaddingClass = 'w-full px-4 sm:px-6 lg:px-10 xl:px-12 py-8'

export const staggerContainer = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: { staggerChildren: 0.06, delayChildren: 0.05 },
  },
}

export const staggerItem = {
  hidden: { opacity: 0, y: 16 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.35, ease: 'easeOut' } },
}

export function getAcwrZone(acwr) {
  if (acwr == null) {
    return {
      label: 'Insufficient Data',
      textClass: 'text-slate-500 dark:text-slate-400',
      badgeClass: 'bg-slate-100 text-slate-500 dark:bg-gray-700 dark:text-slate-300',
      gaugeColor: '#94a3b8',
    }
  }
  if (acwr < 0.8) {
    return {
      label: 'Recovery',
      textClass: 'text-recovery',
      badgeClass: 'bg-blue-100 text-recovery dark:bg-blue-950/50 dark:text-recovery',
      gaugeColor: '#6b9ac4',
    }
  }
  if (acwr <= 1.3) {
    return {
      label: 'Sweet Spot',
      textClass: 'text-sage',
      badgeClass: 'bg-emerald-100 text-sage dark:bg-sage/20 dark:text-sage-muted',
      gaugeColor: '#6b9080',
    }
  }
  if (acwr <= 1.5) {
    return {
      label: 'Caution',
      textClass: 'text-amber-status',
      badgeClass: 'bg-amber-100 text-amber-status dark:bg-amber-950/50 dark:text-amber-status',
      gaugeColor: '#d4a574',
    }
  }
  return {
    label: 'High Risk',
    textClass: 'text-danger-muted',
    badgeClass: 'bg-red-100 text-danger-muted dark:bg-red-950/50 dark:text-danger-muted',
    gaugeColor: '#c1777a',
  }
}
