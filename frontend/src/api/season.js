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
