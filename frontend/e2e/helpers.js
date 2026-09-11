/** Shared mock user + API route fixtures for Playwright critical flows. */

export const MOCK_TOKEN = 'e2e-mock-token'

export function mockUser(overrides = {}) {
  const profileOverrides = overrides.profile || {}
  return {
    id: 1,
    email: 'athlete@example.com',
    email_verified: true,
    ...overrides,
    profile: {
      id: 42,
      name: 'Test Athlete',
      age: 30,
      weight: 70,
      onboarding_completed: true,
      strava_onboarding_done: true,
      coros_onboarding_done: true,
      units: 'metric',
      profile_completeness: 80,
      sports: [],
      injuries: [],
      ...profileOverrides,
    },
  }
}

function json(route, body, status = 200) {
  return route.fulfill({
    status,
    contentType: 'application/json',
    body: JSON.stringify(body),
  })
}

/** Match only the backend API origin — never Vite modules under `/src/api/`. */
function isBackendApi(url) {
  return (
    (url.hostname === '127.0.0.1' || url.hostname === 'localhost') &&
    url.port === '8000' &&
    url.pathname.startsWith('/api/')
  )
}

/**
 * Intercept backend API calls so e2e does not need Postgres or AI providers.
 * Override specific paths via `handlers` (pathname → fulfill fn or body).
 */
export async function installApiMocks(page, { user = mockUser(), handlers = {} } = {}) {
  await page.route(isBackendApi, async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    const { pathname } = url
    const method = request.method()
    const key = `${method} ${pathname}`

    if (typeof handlers[key] === 'function') {
      return handlers[key](route, request)
    }
    if (handlers[key] !== undefined) {
      return json(route, handlers[key])
    }
    if (typeof handlers[pathname] === 'function') {
      return handlers[pathname](route, request)
    }
    if (handlers[pathname] !== undefined) {
      return json(route, handlers[pathname])
    }

    if (pathname === '/api/auth/login' && method === 'POST') {
      return json(route, {
        access_token: MOCK_TOKEN,
        token_type: 'bearer',
        user,
      })
    }

    if (pathname === '/api/auth/register' && method === 'POST') {
      return json(route, {
        access_token: MOCK_TOKEN,
        token_type: 'bearer',
        user,
      })
    }

    if (pathname === '/api/auth/me' && method === 'GET') {
      return json(route, user)
    }

    if (pathname === '/api/coach/status' && method === 'GET') {
      return json(route, {
        providers_configured: [],
        active_provider: null,
        active_model: null,
        fallback_provider: null,
        mode: 'rules',
        ai_consent: true,
        science_chunks: 0,
        has_active_plan: false,
      })
    }

    if (pathname === '/api/coach/plan' && method === 'GET') {
      return json(route, null)
    }

    if (pathname === '/api/coach/chat' && method === 'GET') {
      return json(route, { messages: [] })
    }

    if (pathname === '/api/coach/warm' && method === 'GET') {
      return json(route, {
        context: null,
        proactive_prompts: [],
        todays_call: null,
      })
    }

    if (pathname === '/api/coach/advice' && method === 'GET') {
      return json(route, null)
    }

    if (pathname === '/api/coach/todays-call' && method === 'GET') {
      return json(route, null)
    }

    if (pathname === '/api/coach/context' && method === 'GET') {
      return json(route, null)
    }

    if (pathname === '/api/coros/overview' && method === 'GET') {
      return json(route, {
        connected: false,
        today_health: null,
        fitness: null,
        training_load: { daily_comments: [] },
        schedule: [],
      })
    }

    if (pathname === '/api/strava/status' && method === 'GET') {
      return json(route, { connected: false })
    }

    if (pathname === '/api/athlete/stats' && method === 'GET') {
      return json(route, { weekly_volume_history: [] })
    }

    if (pathname === '/api/activities' && method === 'GET') {
      return json(route, { items: [], total: 0, page: 1, page_size: 10 })
    }

    if (pathname === '/api/cycle/context' && method === 'GET') {
      return json(route, { enabled: false, available: false })
    }

    // Safe fallback so stray calls do not hang the UI.
    if (method === 'GET' || method === 'HEAD') {
      return json(route, {})
    }
    return json(route, { ok: true })
  })
}

/** Seed a stored JWT and mock /api/auth/me so ProtectedRoute treats the session as logged in. */
export async function authenticate(page, options = {}) {
  const user = options.user || mockUser(options.userOverrides)
  await page.addInitScript((token) => {
    window.localStorage.setItem('aal_token', token)
    window.localStorage.setItem('aal_remember', '1')
    window.sessionStorage.removeItem('aal_token')
  }, MOCK_TOKEN)
  await installApiMocks(page, { user, handlers: options.handlers })
  return user
}
