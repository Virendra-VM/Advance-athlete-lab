import { getStoredToken } from './auth'

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

async function handleResponse(response) {
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

export async function getStravaAuthUrl(token = getStoredToken()) {
  const response = await fetch(`${API_BASE_URL}/api/strava/auth`, {
    headers: authHeaders(token),
  })
  return handleResponse(response)
}

export async function completeStravaOAuth(code, state = null, token = getStoredToken()) {
  const response = await fetch(`${API_BASE_URL}/api/strava/callback`, {
    method: 'POST',
    headers: authHeaders(token),
    body: JSON.stringify({ code, state }),
  })
  return handleResponse(response)
}

export async function getStravaConnectionStatus(token = getStoredToken()) {
  const response = await fetch(`${API_BASE_URL}/api/strava/status`, {
    headers: authHeaders(token),
  })
  return handleResponse(response)
}

export async function startStravaSync(token = getStoredToken()) {
  const response = await fetch(`${API_BASE_URL}/api/strava/sync`, {
    method: 'POST',
    headers: authHeaders(token),
  })
  return handleResponse(response)
}

export async function getStravaSyncStatus(token = getStoredToken()) {
  const response = await fetch(`${API_BASE_URL}/api/strava/sync/status`, {
    headers: authHeaders(token),
  })
  return handleResponse(response)
}

export async function backfillStreams(token = getStoredToken()) {
  const response = await fetch(`${API_BASE_URL}/api/strava/backfill-streams`, {
    method: 'POST',
    headers: authHeaders(token),
  })
  return handleResponse(response)
}
