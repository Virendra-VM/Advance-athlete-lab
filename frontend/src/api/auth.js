const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'
const TOKEN_KEY = 'aal_token'
const REMEMBER_KEY = 'aal_remember'
const REMEMBERED_EMAIL_KEY = 'aal_remembered_email'

async function handleResponse(response) {
  if (!response.ok) {
    const errorBody = await response.json().catch(() => ({}))
    const message = errorBody.detail || `Request failed with status ${response.status}`
    throw new Error(typeof message === 'string' ? message : JSON.stringify(message))
  }
  return response.json()
}

function authHeaders(token) {
  return {
    'Content-Type': 'application/json',
    Authorization: `Bearer ${token}`,
  }
}

export function getRememberPreference() {
  return localStorage.getItem(REMEMBER_KEY) !== '0'
}

export function getRememberedEmail() {
  return localStorage.getItem(REMEMBERED_EMAIL_KEY) || ''
}

export function setRememberedEmail(email) {
  if (email) localStorage.setItem(REMEMBERED_EMAIL_KEY, email)
  else localStorage.removeItem(REMEMBERED_EMAIL_KEY)
}

export function getStoredToken() {
  return localStorage.getItem(TOKEN_KEY) || sessionStorage.getItem(TOKEN_KEY)
}

export function setStoredToken(token, remember = true) {
  localStorage.removeItem(TOKEN_KEY)
  sessionStorage.removeItem(TOKEN_KEY)
  localStorage.setItem(REMEMBER_KEY, remember ? '1' : '0')
  if (remember) localStorage.setItem(TOKEN_KEY, token)
  else sessionStorage.setItem(TOKEN_KEY, token)
}

export function clearStoredToken() {
  localStorage.removeItem(TOKEN_KEY)
  sessionStorage.removeItem(TOKEN_KEY)
}

export async function register({ email, password, name }) {
  const response = await fetch(`${API_BASE_URL}/api/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password, name }),
  })
  return handleResponse(response)
}

export async function login({ email, password }) {
  const response = await fetch(`${API_BASE_URL}/api/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  })
  return handleResponse(response)
}

export async function fetchMe(token = getStoredToken()) {
  const response = await fetch(`${API_BASE_URL}/api/auth/me`, {
    headers: authHeaders(token),
  })
  return handleResponse(response)
}

export async function updateProfile(data, token = getStoredToken()) {
  const response = await fetch(`${API_BASE_URL}/api/profile/me`, {
    method: 'PATCH',
    headers: authHeaders(token),
    body: JSON.stringify(data),
  })
  return handleResponse(response)
}

export async function submitOnboarding(data, token = getStoredToken()) {
  const response = await fetch(`${API_BASE_URL}/api/profile/onboarding`, {
    method: 'POST',
    headers: authHeaders(token),
    body: JSON.stringify(data),
  })
  return handleResponse(response)
}

export async function requestEmailVerification(token = getStoredToken()) {
  const response = await fetch(`${API_BASE_URL}/api/auth/verify-email/request`, {
    method: 'POST',
    headers: authHeaders(token),
  })
  return handleResponse(response)
}

export async function confirmEmailVerification(verifyToken) {
  const response = await fetch(`${API_BASE_URL}/api/auth/verify-email/confirm`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ token: verifyToken }),
  })
  return handleResponse(response)
}

export async function completeStravaOnboarding(token = getStoredToken()) {
  const response = await fetch(`${API_BASE_URL}/api/profile/strava-onboarding-complete`, {
    method: 'POST',
    headers: authHeaders(token),
  })
  return handleResponse(response)
}

export async function completeCorosOnboarding(token = getStoredToken()) {
  const response = await fetch(`${API_BASE_URL}/api/profile/coros-onboarding-complete`, {
    method: 'POST',
    headers: authHeaders(token),
  })
  return handleResponse(response)
}
