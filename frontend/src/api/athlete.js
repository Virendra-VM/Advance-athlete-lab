const API_BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

async function handleResponse(response) {
  if (!response.ok) {
    const errorBody = await response.json().catch(() => ({}));
    const message =
      errorBody.detail || `Request failed with status ${response.status}`;
    throw new Error(
      typeof message === "string" ? message : JSON.stringify(message),
    );
  }
  return response.json();
}

export async function getAthleteProfile(id) {
  const response = await fetch(`${API_BASE_URL}/api/athletes/${id}`);
  return handleResponse(response);
}

export async function listAthleteProfiles() {
  const response = await fetch(`${API_BASE_URL}/api/athletes`);
  return handleResponse(response);
}

export async function createAthleteProfile(data) {
  const response = await fetch(`${API_BASE_URL}/api/athletes`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  return handleResponse(response)
}

export async function getAthleteStats(athleteProfileId) {
  const response = await fetch(
    `${API_BASE_URL}/api/athlete/stats?athlete_profile_id=${athleteProfileId}`,
  )
  return handleResponse(response)
}
