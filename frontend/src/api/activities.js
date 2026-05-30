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

export async function uploadStravaHistoryExport(athleteProfileId, file) {
  const formData = new FormData();
  formData.append("athlete_profile_id", String(athleteProfileId));
  formData.append("file", file);

  const response = await fetch(
    `${API_BASE_URL}/api/import/strava-history/upload`,
    {
      method: "POST",
      body: formData,
    },
  );
  return handleResponse(response);
}

export async function startStravaHistoryImport(athleteProfileId) {
  const response = await fetch(`${API_BASE_URL}/api/import/strava-history`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ athlete_profile_id: athleteProfileId }),
  });
  return handleResponse(response);
}

export async function getImportStatus() {
  const response = await fetch(
    `${API_BASE_URL}/api/import/strava-history/status`,
  );
  return handleResponse(response);
}

export async function listActivities(athleteProfileId) {
  const response = await fetch(
    `${API_BASE_URL}/api/activities?athlete_profile_id=${athleteProfileId}`,
  );
  return handleResponse(response);
}

export async function getActivity(activityId) {
  const response = await fetch(`${API_BASE_URL}/api/activities/${activityId}`);
  return handleResponse(response);
}

export async function getActivityPoints(activityId) {
  const response = await fetch(`${API_BASE_URL}/api/activities/${activityId}/points`);
  return handleResponse(response);
}

export async function getActivitySummary(athleteProfileId) {
  const response = await fetch(
    `${API_BASE_URL}/api/activities/summary?athlete_profile_id=${athleteProfileId}`,
  );
  return handleResponse(response);
}

export async function backfillActivityMetadata(athleteProfileId) {
  const response = await fetch(
    `${API_BASE_URL}/api/import/strava-history/backfill-metadata?athlete_profile_id=${athleteProfileId}`,
    { method: "POST" },
  );
  return handleResponse(response);
}
