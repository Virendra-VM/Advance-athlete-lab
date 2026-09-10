import { getStoredToken } from './auth'

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

async function handleResponse(response) {
  if (response.status === 204) return null
  if (!response.ok) {
    const errorBody = await response.json().catch(() => ({}))
    const message = errorBody.detail || `Request failed with status ${response.status}`
    const error = new Error(typeof message === 'string' ? message : JSON.stringify(message))
    error.status = response.status
    throw error
  }
  return response.json()
}

function authHeaders(token = getStoredToken()) {
  return {
    'Content-Type': 'application/json',
    Authorization: `Bearer ${token}`,
  }
}

export async function getCoachStatus(token = getStoredToken()) {
  const response = await fetch(`${API_BASE_URL}/api/coach/status`, {
    headers: authHeaders(token),
  })
  return handleResponse(response)
}

export async function getWeekPlan(weekStart, token = getStoredToken()) {
  const query = weekStart ? `?week_start=${encodeURIComponent(weekStart)}` : ''
  const response = await fetch(`${API_BASE_URL}/api/coach/plan${query}`, {
    headers: authHeaders(token),
  })
  return handleResponse(response)
}

function athleteTimezone() {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC'
  } catch {
    return 'UTC'
  }
}

export async function generateWeekPlan(weekStart, token = getStoredToken()) {
  const response = await fetch(`${API_BASE_URL}/api/coach/plan`, {
    method: 'POST',
    headers: authHeaders(token),
    body: JSON.stringify({ week_start: weekStart ?? null, timezone: athleteTimezone() }),
  })
  return handleResponse(response)
}

export async function addWeekPlanToSchedule(planId, token = getStoredToken()) {
  const response = await fetch(`${API_BASE_URL}/api/coach/plan/${planId}/schedule`, {
    method: 'POST',
    headers: authHeaders(token),
  })
  return handleResponse(response)
}

export async function applyChatWeek(
  { messageId, markdown, publish = true } = {},
  token = getStoredToken(),
) {
  const response = await fetch(`${API_BASE_URL}/api/coach/plan/from-chat`, {
    method: 'POST',
    headers: authHeaders(token),
    body: JSON.stringify({
      message_id: messageId ?? null,
      markdown: markdown ?? null,
      publish,
      timezone: athleteTimezone(),
    }),
  })
  return handleResponse(response)
}

export async function getTodaysCall(token = getStoredToken()) {
  const response = await fetch(`${API_BASE_URL}/api/coach/todays-call`, {
    headers: authHeaders(token),
  })
  return handleResponse(response)
}

export async function getDailyAdvice(options = {}, token = getStoredToken()) {
  if (typeof options === 'string') {
    token = options
    options = {}
  }
  const params = new URLSearchParams({ timezone: athleteTimezone() })
  if (options.refresh) params.set('refresh', 'true')
  const response = await fetch(`${API_BASE_URL}/api/coach/advice?${params}`, {
    headers: authHeaders(token),
  })
  return handleResponse(response)
}

export async function getWeekBrief(options = {}, token = getStoredToken()) {
  if (typeof options === 'string') {
    token = options
    options = {}
  }
  const params = new URLSearchParams({ timezone: athleteTimezone() })
  if (options.refresh) params.set('refresh', 'true')
  if (options.topic) params.set('topic', options.topic)
  const response = await fetch(`${API_BASE_URL}/api/coach/week-brief?${params}`, {
    headers: authHeaders(token),
  })
  return handleResponse(response)
}

export async function getChatHistory(token = getStoredToken()) {
  const response = await fetch(`${API_BASE_URL}/api/coach/chat`, {
    headers: authHeaders(token),
  })
  return handleResponse(response)
}

export async function getWeekPlanContext(token = getStoredToken()) {
  const params = new URLSearchParams({ timezone: athleteTimezone() })
  const response = await fetch(`${API_BASE_URL}/api/coach/week-plan/context?${params}`, {
    headers: authHeaders(token),
  })
  return handleResponse(response)
}

export async function sendChatMessage(message, tokenOrOptions = getStoredToken(), options = {}) {
  let token = tokenOrOptions
  if (tokenOrOptions && typeof tokenOrOptions === 'object') {
    options = tokenOrOptions
    token = options.token || getStoredToken()
  }
  const body = { message, timezone: athleteTimezone() }
  if (options.activityId) body.activity_id = options.activityId
  if (options.chatMode) body.chat_mode = options.chatMode
  const response = await fetch(`${API_BASE_URL}/api/coach/chat`, {
    method: 'POST',
    headers: authHeaders(token),
    body: JSON.stringify(body),
    signal: options.signal,
  })
  return handleResponse(response)
}

export async function getCoachPlannedWorkouts(fromDate, toDate, token = getStoredToken()) {
  const params = new URLSearchParams()
  if (fromDate) params.set('from', fromDate)
  if (toDate) params.set('to', toDate)
  const query = params.toString()
  const response = await fetch(
    `${API_BASE_URL}/api/coach/planned-workouts${query ? `?${query}` : ''}`,
    { headers: authHeaders(token) },
  )
  return handleResponse(response)
}

export async function confirmWearableBaseline(token = getStoredToken()) {
  const response = await fetch(`${API_BASE_URL}/api/coach/baseline/confirm`, {
    method: 'POST',
    headers: authHeaders(token),
  })
  return handleResponse(response)
}

export async function repeatWorkout(workoutId, targetDate, token = getStoredToken()) {
  const response = await fetch(`${API_BASE_URL}/api/coach/workouts/${workoutId}/repeat`, {
    method: 'POST',
    headers: authHeaders(token),
    body: JSON.stringify({ target_date: targetDate ?? null }),
  })
  return handleResponse(response)
}

export async function getWorkoutCompliance(workoutId, token = getStoredToken()) {
  const response = await fetch(`${API_BASE_URL}/api/coach/workouts/${workoutId}/compliance`, {
    headers: authHeaders(token),
  })
  return handleResponse(response)
}

export async function getFavoriteTemplates(token = getStoredToken()) {
  const response = await fetch(`${API_BASE_URL}/api/coach/library/favorites`, {
    headers: authHeaders(token),
  })
  return handleResponse(response)
}

export async function addFavoriteTemplate(templateId, token = getStoredToken()) {
  const response = await fetch(`${API_BASE_URL}/api/coach/library/favorites/${encodeURIComponent(templateId)}`, {
    method: 'POST',
    headers: authHeaders(token),
  })
  return handleResponse(response)
}

export async function removeFavoriteTemplate(templateId, token = getStoredToken()) {
  const response = await fetch(`${API_BASE_URL}/api/coach/library/favorites/${encodeURIComponent(templateId)}`, {
    method: 'DELETE',
    headers: authHeaders(token),
  })
  return handleResponse(response)
}

export async function exportWorkout(workoutId, format = 'fit', token = getStoredToken()) {
  const params = new URLSearchParams({ format })
  const response = await fetch(
    `${API_BASE_URL}/api/coach/workouts/${workoutId}/export?${params}`,
    { headers: authHeaders(token) },
  )
  if (!response.ok) {
    const errorBody = await response.json().catch(() => ({}))
    const message = errorBody.detail || `Export failed with status ${response.status}`
    throw new Error(typeof message === 'string' ? message : JSON.stringify(message))
  }
  const blob = await response.blob()
  const disposition = response.headers.get('Content-Disposition') || ''
  const match = disposition.match(/filename=\"?([^\";]+)\"?/)
  const filename = match ? match[1] : `workout.${format}`
  return { blob, filename }
}
