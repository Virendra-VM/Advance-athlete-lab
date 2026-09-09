import { getStoredToken } from './auth'

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

async function handleResponse(response) {
  if (response.status === 204) return null
  if (!response.ok) {
    const errorBody = await response.json().catch(() => ({}))
    const message = errorBody.detail || `Request failed with status ${response.status}`
    throw new Error(typeof message === 'string' ? message : JSON.stringify(message))
  }
  return response.json()
}

function authHeaders(token = getStoredToken()) {
  return {
    'Content-Type': 'application/json',
    Authorization: `Bearer ${token}`,
  }
}

export async function getSeason(token = getStoredToken()) {
  const response = await fetch(`${API_BASE_URL}/api/season`, {
    headers: authHeaders(token),
  })
  return handleResponse(response)
}

export async function getSeasonPreview(token = getStoredToken()) {
  const response = await fetch(`${API_BASE_URL}/api/season/preview`, {
    headers: authHeaders(token),
  })
  return handleResponse(response)
}

export async function generateSeason(token = getStoredToken()) {
  const response = await fetch(`${API_BASE_URL}/api/season/generate`, {
    method: 'POST',
    headers: authHeaders(token),
  })
  return handleResponse(response)
}

export async function listEvents(token = getStoredToken()) {
  const response = await fetch(`${API_BASE_URL}/api/season/events`, {
    headers: authHeaders(token),
  })
  return handleResponse(response)
}

export async function createEvent(payload, token = getStoredToken()) {
  const response = await fetch(`${API_BASE_URL}/api/season/events`, {
    method: 'POST',
    headers: authHeaders(token),
    body: JSON.stringify(payload),
  })
  return handleResponse(response)
}

export async function updateEvent(eventId, payload, token = getStoredToken()) {
  const response = await fetch(`${API_BASE_URL}/api/season/events/${eventId}`, {
    method: 'PATCH',
    headers: authHeaders(token),
    body: JSON.stringify(payload),
  })
  return handleResponse(response)
}

export async function deleteEvent(eventId, token = getStoredToken()) {
  const response = await fetch(`${API_BASE_URL}/api/season/events/${eventId}`, {
    method: 'DELETE',
    headers: authHeaders(token),
  })
  return handleResponse(response)
}

export async function completeEvent(eventId, payload, token = getStoredToken()) {
  const response = await fetch(`${API_BASE_URL}/api/season/events/${eventId}/complete`, {
    method: 'POST',
    headers: authHeaders(token),
    body: JSON.stringify(payload),
  })
  return handleResponse(response)
}

export async function getEventProtocol(eventId, token = getStoredToken()) {
  const response = await fetch(`${API_BASE_URL}/api/season/events/${eventId}/protocol`, {
    headers: authHeaders(token),
  })
  return handleResponse(response)
}

export async function getSeasonAudit(token = getStoredToken()) {
  const response = await fetch(`${API_BASE_URL}/api/season/audit`, {
    headers: authHeaders(token),
  })
  return handleResponse(response)
}

export async function getReplanTriggers(token = getStoredToken()) {
  const response = await fetch(`${API_BASE_URL}/api/season/replan/triggers`, {
    headers: authHeaders(token),
  })
  return handleResponse(response)
}

export async function replanSeason(payload = {}, token = getStoredToken()) {
  const response = await fetch(`${API_BASE_URL}/api/season/replan`, {
    method: 'POST',
    headers: authHeaders(token),
    body: JSON.stringify(payload),
  })
  return handleResponse(response)
}

export async function adjustSeasonPhase(phaseId, deltaWeeks, token = getStoredToken()) {
  const response = await fetch(`${API_BASE_URL}/api/season/phases/${phaseId}`, {
    method: 'PATCH',
    headers: authHeaders(token),
    body: JSON.stringify({ delta_weeks: deltaWeeks }),
  })
  return handleResponse(response)
}

export async function shiftRecoveryPhase(phaseId, targetWeekStart, token = getStoredToken()) {
  const response = await fetch(`${API_BASE_URL}/api/season/phases/${phaseId}/shift`, {
    method: 'POST',
    headers: authHeaders(token),
    body: JSON.stringify({ target_week_start: targetWeekStart }),
  })
  return handleResponse(response)
}

export async function replaceSeasonPhase(phaseId, phaseType, token = getStoredToken()) {
  const response = await fetch(`${API_BASE_URL}/api/season/phases/${phaseId}/replace`, {
    method: 'POST',
    headers: authHeaders(token),
    body: JSON.stringify({ phase_type: phaseType }),
  })
  return handleResponse(response)
}

export async function deleteSeasonPhase(phaseId, mergeInto = 'next', token = getStoredToken()) {
  const response = await fetch(`${API_BASE_URL}/api/season/phases/${phaseId}`, {
    method: 'DELETE',
    headers: authHeaders(token),
    body: JSON.stringify({ merge_into: mergeInto }),
  })
  return handleResponse(response)
}
