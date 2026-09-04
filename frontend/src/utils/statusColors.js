export const cardShellClass =
  'rounded-2xl border border-[var(--aal-line)] bg-[var(--aal-card)] shadow-sm'

export const pageShellClass =
  'min-h-screen w-full bg-[var(--aal-bg)] text-[var(--aal-ink)]'

export const pagePaddingClass = 'w-full px-4 py-6 sm:px-6 lg:px-8'

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
      id: 'empty',
      label: 'Need more data',
      shortLabel: '—',
      textClass: 'text-[var(--aal-muted)]',
      badgeClass: 'bg-slate-100 text-slate-500 dark:bg-white/10 dark:text-slate-300',
      gaugeColor: '#94a3b8',
      tone: 'default',
    }
  }
  if (acwr < 0.8) {
    return {
      id: 'recovery',
      label: 'Underloaded',
      shortLabel: 'Light week',
      textClass: 'text-recovery',
      badgeClass: 'bg-blue-100 text-recovery dark:bg-blue-950/50 dark:text-recovery',
      gaugeColor: '#6b9ac4',
      tone: 'default',
    }
  }
  if (acwr <= 1.3) {
    return {
      id: 'sweet',
      label: 'Sweet spot',
      shortLabel: 'Productive',
      textClass: 'text-sage',
      badgeClass: 'bg-emerald-100 text-sage dark:bg-sage/20 dark:text-sage-muted',
      gaugeColor: '#6b9080',
      tone: 'good',
    }
  }
  if (acwr <= 1.5) {
    return {
      id: 'caution',
      label: 'Caution',
      shortLabel: 'Spiking',
      textClass: 'text-amber-status',
      badgeClass: 'bg-amber-100 text-amber-status dark:bg-amber-950/50 dark:text-amber-status',
      gaugeColor: '#d4a574',
      tone: 'warn',
    }
  }
  return {
    id: 'high',
    label: 'High risk',
    shortLabel: 'Too fast',
    textClass: 'text-danger-muted',
    badgeClass: 'bg-red-100 text-danger-muted dark:bg-red-950/50 dark:text-danger-muted',
    gaugeColor: '#c1777a',
    tone: 'bad',
  }
}
