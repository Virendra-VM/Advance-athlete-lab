const STORAGE_PREFIX = 'aal_coach_pins_'
const MAX_PINS = 8

function preview(text, limit = 48) {
  const value = String(text || '')
    .replace(/\s+/g, ' ')
    .trim()
  if (!value) return 'Pinned'
  return value.length <= limit ? value : `${value.slice(0, limit).trim()}…`
}

export function loadPins(profileId) {
  if (!profileId) return []
  try {
    const parsed = JSON.parse(localStorage.getItem(`${STORAGE_PREFIX}${profileId}`) || '[]')
    return Array.isArray(parsed) ? parsed.filter((pin) => pin?.id) : []
  } catch {
    return []
  }
}

export function savePins(profileId, pins) {
  if (!profileId) return
  localStorage.setItem(`${STORAGE_PREFIX}${profileId}`, JSON.stringify(pins.slice(0, MAX_PINS)))
}

export function pinFromMessage(message) {
  return {
    id: `msg-${message.id}`,
    type: 'message',
    messageId: message.id,
    role: message.role,
    content: message.content,
    created_at: message.created_at,
    label: preview(message.content),
  }
}

export function pinFromWeek(plan, weekStart) {
  const title = plan?.plan?.title || 'This week'
  return {
    id: `week-${weekStart}`,
    type: 'week',
    planId: plan?.plan_id ?? null,
    weekStart,
    title,
    summary: plan?.plan?.summary || '',
    content: plan?.plan?.summary || title,
    label: preview(title, 36),
  }
}

export function upsertPin(pins, pin) {
  const without = pins.filter((item) => item.id !== pin.id)
  return [pin, ...without].slice(0, MAX_PINS)
}

export function removePin(pins, pinId) {
  return pins.filter((item) => item.id !== pinId)
}
