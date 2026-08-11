import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { completeStravaOAuth, startStravaSync } from '../api/strava'
import { useAuth } from '../context/AuthContext'
import { pageShellClass } from '../utils/statusColors'
import Navigation from './Navigation'
import Card from './ui/Card'

// Shared across Strict Mode remounts so exchange + follow-up run once per code.
const stravaFlowPromises = new Map()

function readStravaCallbackParams() {
  const params = new URLSearchParams(window.location.search)
  const error = params.get('error')
  const code = params.get('code')
  const state = params.get('state')

  if (code || error) {
    sessionStorage.setItem(
      'strava_oauth_callback',
      JSON.stringify({ error, code, state }),
    )
    window.history.replaceState({}, '', window.location.pathname)
  }

  const cached = sessionStorage.getItem('strava_oauth_callback')
  if (!cached) return { error: null, code: null, state: null }
  try {
    return JSON.parse(cached)
  } catch {
    return { error: null, code: null, state: null }
  }
}

export default function StravaCallback() {
  const navigate = useNavigate()
  const { isAuthenticated, refreshUser, markStravaOnboardingDone } = useAuth()
  const [status, setStatus] = useState('loading')
  const [message, setMessage] = useState('Connecting your Strava account...')

  useEffect(() => {
    const { error, code, state } = readStravaCallbackParams()

    if (error) {
      setStatus('error')
      setMessage(`Strava authorization failed: ${error}`)
      return
    }

    if (!code) {
      setStatus('error')
      setMessage('Missing authorization code from Strava.')
      return
    }

    if (!stravaFlowPromises.has(code)) {
      stravaFlowPromises.set(
        code,
        (async () => {
          const connection = await completeStravaOAuth(code, state)

          // Capture auth helpers at start of the single flow; do not re-run from effect deps.
          if (isAuthenticated) {
            await refreshUser()
            await markStravaOnboardingDone()
          }

          // Backend callback often already started sync; 409 means it's running.
          if (connection?.athlete_profile_id) {
            try {
              await startStravaSync(connection.athlete_profile_id)
            } catch {
              // ignore — sync already running or will be retried from dashboard
            }
          }

          sessionStorage.removeItem('strava_oauth_callback')
          return { connected: true, isAuthenticated }
        })().catch((err) => {
          stravaFlowPromises.delete(code)
          throw err
        }),
      )
    }

    let cancelled = false
    stravaFlowPromises
      .get(code)
      .then((result) => {
        if (cancelled) return
        setStatus('success')
        setMessage('Strava connected! Syncing your activities...')
        setTimeout(
          () => navigate(result?.isAuthenticated ? '/connect-coros' : '/signin'),
          2000,
        )
      })
      .catch((err) => {
        if (cancelled) return
        setStatus('error')
        setMessage(err.message || 'Failed to connect Strava account.')
      })

    return () => {
      cancelled = true
    }
    // Run once on mount. Auth helpers are captured inside the single shared flow promise.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [navigate])

  return (
    <div className={pageShellClass}>
      <Navigation showProfileLink={false} />
      <main className="flex min-h-[calc(100vh-80px)] items-center justify-center px-6">
        <Card className="w-full max-w-lg p-8 text-center">
          <p className="text-sm font-semibold uppercase tracking-widest text-sage">Strava Integration</p>
          <h1 className="mt-3 text-2xl font-bold text-slate-900 dark:text-white">
            {status === 'loading' && 'Connecting...'}
            {status === 'success' && 'Connected'}
            {status === 'error' && 'Connection Failed'}
          </h1>
          <p className="mt-4 text-slate-600 dark:text-slate-400">{message}</p>
        </Card>
      </main>
    </div>
  )
}
