const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

async function handleResponse(response) {
  if (!response.ok) {
    const errorBody = await response.json().catch(() => ({}))
    const message = errorBody.detail || `Request failed with status ${response.status}`
    throw new Error(typeof message === 'string' ? message : JSON.stringify(message))
  }
  return response.json()
}

export async function getStravaAuthUrl(athleteProfileId) {
  const params = athleteProfileId ? `?athlete_profile_id=${athleteProfileId}` : ''
  const response = await fetch(`${API_BASE_URL}/api/strava/auth${params}`)
  return handleResponse(response)
}

export async function completeStravaOAuth(code, state = null) {
  const response = await fetch(`${API_BASE_URL}/api/strava/callback`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ code, state }),
  })
  return handleResponse(response)
}

export async function getStravaConnectionStatus(athleteProfileId) {
  const params = athleteProfileId ? `?athlete_profile_id=${athleteProfileId}` : ''
  const response = await fetch(`${API_BASE_URL}/api/strava/status${params}`)
  return handleResponse(response)
}
