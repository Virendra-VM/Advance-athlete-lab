const STORAGE_PREFIX = 'aal_coach_composer_'

function storageKey(profileId) {
  return `${STORAGE_PREFIX}${profileId || 'anon'}`
}

export function loadComposerStorage(profileId) {
  if (!profileId) return null
  try {
    const raw = sessionStorage.getItem(storageKey(profileId))
    if (!raw) return null
    const parsed = JSON.parse(raw)
    return parsed && typeof parsed === 'object' ? parsed : null
  } catch {
    return null
  }
}

export function loadComposerDraft(profileId) {
  const stored = loadComposerStorage(profileId)
  return typeof stored?.draft === 'string' ? stored.draft : ''
}

export function saveComposerDraft(profileId, draft) {
  if (!profileId) return
  const current = loadComposerStorage(profileId) || {}
  sessionStorage.setItem(
    storageKey(profileId),
    JSON.stringify({ ...current, draft: draft ?? '' }),
  )
}

export function saveWeekFlowState(profileId, flow) {
  if (!profileId) return
  const current = loadComposerStorage(profileId) || {}
  sessionStorage.setItem(
    storageKey(profileId),
    JSON.stringify({
      ...current,
      weekFlowStep: flow.weekFlowStep ?? null,
      weekConstraints: flow.weekConstraints ?? '',
      recoveryShift: Boolean(flow.recoveryShift),
      recoveryPhase: flow.recoveryPhase ?? null,
    }),
  )
}

export function clearWeekFlowState(profileId) {
  if (!profileId) return
  const current = loadComposerStorage(profileId) || {}
  sessionStorage.setItem(
    storageKey(profileId),
    JSON.stringify({
      ...current,
      weekFlowStep: null,
      weekConstraints: '',
      recoveryShift: false,
      recoveryPhase: null,
    }),
  )
}
