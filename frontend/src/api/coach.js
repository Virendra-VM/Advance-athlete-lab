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

export async function getDailyAdvice(token = getStoredToken()) {
  const params = new URLSearchParams({ timezone: athleteTimezone() })
  const response = await fetch(`${API_BASE_URL}/api/coach/advice?${params}`, {
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

export async function sendChatMessage(message, token = getStoredToken()) {
  const response = await fetch(`${API_BASE_URL}/api/coach/chat`, {
    method: 'POST',
    headers: authHeaders(token),
    body: JSON.stringify({ message, timezone: athleteTimezone() }),
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
