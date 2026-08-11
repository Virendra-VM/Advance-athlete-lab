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

export async function getCorosAuthUrl(token = getStoredToken()) {
  const response = await fetch(`${API_BASE_URL}/api/coros/auth`, {
    headers: authHeaders(token),
  })
  return handleResponse(response)
}

export async function completeCorosOAuth(code, state, token = getStoredToken()) {
  const response = await fetch(`${API_BASE_URL}/api/coros/callback`, {
    method: 'POST',
    headers: authHeaders(token),
    body: JSON.stringify({ code, state }),
  })
  return handleResponse(response)
}

export async function getCorosConnectionStatus(token = getStoredToken()) {
  const response = await fetch(`${API_BASE_URL}/api/coros/status`, {
    headers: authHeaders(token),
  })
  return handleResponse(response)
}

export async function startCorosSync(token = getStoredToken()) {
  const response = await fetch(`${API_BASE_URL}/api/coros/sync`, {
    method: 'POST',
    headers: authHeaders(token),
  })
  return handleResponse(response)
}

export async function getCorosSyncStatus(token = getStoredToken()) {
  const response = await fetch(`${API_BASE_URL}/api/coros/sync/status`, {
    headers: authHeaders(token),
  })
  return handleResponse(response)
}

export async function getCorosOverview(token = getStoredToken()) {
  const response = await fetch(`${API_BASE_URL}/api/coros/overview`, {
    headers: authHeaders(token),
  })
  return handleResponse(response)
}

export async function getCorosSchedule(fromDate, toDate, token = getStoredToken()) {
  const params = new URLSearchParams()
  if (fromDate) params.set('from', fromDate)
  if (toDate) params.set('to', toDate)
  const query = params.toString()
  const response = await fetch(
    `${API_BASE_URL}/api/coros/schedule${query ? `?${query}` : ''}`,
    { headers: authHeaders(token) },
  )
  return handleResponse(response)
}

export async function disconnectCoros(token = getStoredToken()) {
  const response = await fetch(`${API_BASE_URL}/api/coros/disconnect`, {
    method: 'DELETE',
    headers: authHeaders(token),
  })
  return handleResponse(response)
}

export async function getCoachContext(token = getStoredToken()) {
  const response = await fetch(`${API_BASE_URL}/api/coach/context`, {
    headers: authHeaders(token),
  })
  return handleResponse(response)
}

export async function getMetricSeries(metric, range = '4w', token = getStoredToken()) {
  const response = await fetch(
    `${API_BASE_URL}/api/coros/metrics/${metric}?range=${encodeURIComponent(range)}`,
    { headers: authHeaders(token) },
  )
  return handleResponse(response)
}

export async function backfillMetricHistory(metric, range = '3m', token = getStoredToken()) {
  const response = await fetch(`${API_BASE_URL}/api/coros/metrics/${metric}/history`, {
    method: 'POST',
    headers: authHeaders(token),
    body: JSON.stringify({ metric, range }),
  })
  return handleResponse(response)
}

export async function getCorosDevices(token = getStoredToken()) {
  const response = await fetch(`${API_BASE_URL}/api/coros/devices`, {
    headers: authHeaders(token),
  })
  return handleResponse(response)
}

export async function getCorosCycleLatest(token = getStoredToken()) {
  const response = await fetch(`${API_BASE_URL}/api/coros/cycle/latest`, {
    headers: authHeaders(token),
  })
  return handleResponse(response)
}

export async function backfillCorosFit(limit = 10, token = getStoredToken()) {
  const response = await fetch(
    `${API_BASE_URL}/api/coros/backfill-fit?limit=${encodeURIComponent(String(limit))}`,
    {
      method: 'POST',
      headers: authHeaders(token),
    },
  )
  return handleResponse(response)
}

export async function backfillCorosFitForActivity(activityId, token = getStoredToken()) {
  const response = await fetch(`${API_BASE_URL}/api/coros/activities/${activityId}/fit`, {
    method: 'POST',
    headers: authHeaders(token),
  })
  return handleResponse(response)
}
