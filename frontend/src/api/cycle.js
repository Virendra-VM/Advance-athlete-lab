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

export async function getCycleContext(token = getStoredToken()) {
  const response = await fetch(`${API_BASE_URL}/api/cycle/context`, {
    headers: authHeaders(token),
  })
  return handleResponse(response)
}

export async function logPeriodStart(periodStartDate, token = getStoredToken()) {
  const response = await fetch(`${API_BASE_URL}/api/cycle/period-starts`, {
    method: 'POST',
    headers: authHeaders(token),
    body: JSON.stringify({ period_start_date: periodStartDate }),
  })
  return handleResponse(response)
}
