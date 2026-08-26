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

export async function uploadStravaHistoryExport(athleteProfileId, file) {
  const formData = new FormData()
  formData.append('athlete_profile_id', String(athleteProfileId))
  formData.append('file', file)

  const response = await fetch(`${API_BASE_URL}/api/import/strava-history/upload`, {
    method: 'POST',
    body: formData,
  })
  return handleResponse(response)
}

export async function startStravaHistoryImport(athleteProfileId) {
  const response = await fetch(`${API_BASE_URL}/api/import/strava-history`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ athlete_profile_id: athleteProfileId }),
  })
  return handleResponse(response)
}

export async function getImportStatus() {
  const response = await fetch(`${API_BASE_URL}/api/import/strava-history/status`)
  return handleResponse(response)
}

export async function listActivities(athleteProfileId, params = {}) {
  const search = new URLSearchParams({
    athlete_profile_id: String(athleteProfileId),
    page: String(params.page || 1),
    page_size: String(params.page_size || 10),
    sort: params.sort || 'date_desc',
  })
  if (params.q) search.set('q', params.q)
  if (params.sport) search.set('sport', params.sport)
  if (params.provider) search.set('provider', params.provider)
  if (params.from) search.set('from', params.from)
  if (params.to) search.set('to', params.to)
  if (params.include_duplicates) search.set('include_duplicates', 'true')

  const response = await fetch(`${API_BASE_URL}/api/activities?${search.toString()}`)
  return handleResponse(response)
}

export async function dedupeActivities(token = getStoredToken()) {
  const response = await fetch(`${API_BASE_URL}/api/activities/dedupe`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
  })
  return handleResponse(response)
}

export async function getActivity(activityId) {
  const response = await fetch(`${API_BASE_URL}/api/activities/${activityId}`)
  return handleResponse(response)
}

export async function enrichActivityDetail(activityId, { force = false } = {}) {
  const search = force ? '?force=true' : ''
  const response = await fetch(`${API_BASE_URL}/api/activities/${activityId}/enrich${search}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${getStoredToken()}`,
    },
  })
  return handleResponse(response)
}

export async function getActivityPoints(activityId) {
  const response = await fetch(`${API_BASE_URL}/api/activities/${activityId}/points`)
  return handleResponse(response)
}

export async function updateActivityNotes(activityId, notes) {
  const response = await fetch(`${API_BASE_URL}/api/activities/${activityId}/notes`, {
    method: 'PATCH',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${getStoredToken()}`,
    },
    body: JSON.stringify({ notes }),
  })
  return handleResponse(response)
}

export async function listActivityNotes(activityId) {
  const response = await fetch(`${API_BASE_URL}/api/activities/${activityId}/notes`, {
    headers: { Authorization: `Bearer ${getStoredToken()}` },
  })
  return handleResponse(response)
}

export async function createActivityNote(activityId, body) {
  const response = await fetch(`${API_BASE_URL}/api/activities/${activityId}/notes`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${getStoredToken()}`,
    },
    body: JSON.stringify({ body }),
  })
  return handleResponse(response)
}

export async function updateActivityNote(activityId, noteId, body) {
  const response = await fetch(`${API_BASE_URL}/api/activities/${activityId}/notes/${noteId}`, {
    method: 'PATCH',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${getStoredToken()}`,
    },
    body: JSON.stringify({ body }),
  })
  return handleResponse(response)
}

export async function deleteActivityNote(activityId, noteId) {
  const response = await fetch(`${API_BASE_URL}/api/activities/${activityId}/notes/${noteId}`, {
    method: 'DELETE',
    headers: { Authorization: `Bearer ${getStoredToken()}` },
  })
  if (!response.ok) {
    const errorBody = await response.json().catch(() => ({}))
    const message = errorBody.detail || `Request failed with status ${response.status}`
    throw new Error(typeof message === 'string' ? message : JSON.stringify(message))
  }
  return true
}

export async function getActivitySummary(athleteProfileId) {
  const response = await fetch(
    `${API_BASE_URL}/api/activities/summary?athlete_profile_id=${athleteProfileId}`,
  )
  return handleResponse(response)
}

export async function backfillActivityMetadata(athleteProfileId) {
  const response = await fetch(
    `${API_BASE_URL}/api/import/strava-history/backfill-metadata?athlete_profile_id=${athleteProfileId}`,
    { method: 'POST' },
  )
  return handleResponse(response)
}
