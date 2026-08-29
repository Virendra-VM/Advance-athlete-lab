import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { completeCorosOAuth, startCorosSync } from '../api/coros'
import { useAuth } from '../context/AuthContext'
import { pageShellClass } from '../utils/statusColors'
import Navigation from './Navigation'
import Card from './ui/Card'

// Shared across Strict Mode remounts so exchange + follow-up run once per code.
const corosFlowPromises = new Map()

function readCorosCallbackParams() {
  const params = new URLSearchParams(window.location.search)
  const error = params.get('error')
  const code = params.get('code')
  const state = params.get('state')

  if (code || error) {
    sessionStorage.setItem(
      'coros_oauth_callback',
      JSON.stringify({ error, code, state }),
    )
    window.history.replaceState({}, '', window.location.pathname)
  }

  const cached = sessionStorage.getItem('coros_oauth_callback')
  if (!cached) return { error: null, code: null, state: null }
  try {
    return JSON.parse(cached)
  } catch {
    return { error: null, code: null, state: null }
  }
}

export default function CorosCallback() {
  const navigate = useNavigate()
  const { isAuthenticated, refreshUser, markCorosOnboardingDone } = useAuth()
  const [status, setStatus] = useState('loading')
  const [message, setMessage] = useState('Connecting your COROS account...')

  useEffect(() => {
    const { error, code, state } = readCorosCallbackParams()

    if (error) {
      setStatus('error')
      setMessage(`COROS authorization failed: ${error}`)
      return
    }

    if (!code || !state) {
      setStatus('error')
      setMessage('Missing authorization code from COROS.')
      return
    }

    if (!isAuthenticated) {
      setStatus('error')
      setMessage('Please sign in before connecting COROS.')
      return
    }

    if (!corosFlowPromises.has(code)) {
      corosFlowPromises.set(
        code,
        (async () => {
          await completeCorosOAuth(code, state)
          await refreshUser()
          await markCorosOnboardingDone()
          try {
            await startCorosSync()
          } catch {
            // ignore — sync may already be running
          }
          sessionStorage.removeItem('coros_oauth_callback')
        })().catch((err) => {
          corosFlowPromises.delete(code)
          throw err
        }),
      )
    }

    let cancelled = false
    corosFlowPromises
      .get(code)
      .then(() => {
        if (cancelled) return
        setStatus('success')
        setMessage('COROS connected! Syncing your health and training data...')
        setTimeout(() => navigate('/dashboard'), 2000)
      })
      .catch((err) => {
        if (cancelled) return
        setStatus('error')
        setMessage(err.message || 'Failed to connect COROS account.')
      })

    return () => {
      cancelled = true
    }
    // Run once when authenticated. Follow-up work lives in the shared flow promise.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [navigate, isAuthenticated])

  return (
    <div className={pageShellClass}>
      <Navigation showProfileLink={false} />
      <main className="flex min-h-[calc(100vh-80px)] items-center justify-center px-6">
        <Card className="w-full max-w-lg p-8 text-center">
          <p className="text-sm font-semibold uppercase tracking-widest text-sage">COROS Integration</p>
          <h1 className="mt-3 text-2xl font-bold text-slate-900 dark:text-white">
            {status === 'loading' && 'Connecting...'}
            {status === 'success' && 'Connected'}
            {status === 'error' && 'Connection Failed'}
          </h1>
          <p className="mt-4 text-slate-600 dark:text-slate-400">{message}</p>
          {status === 'error' && (
            <button
              type="button"
              onClick={() => navigate('/settings')}
              className="mt-6 rounded-xl bg-slate-900 px-5 py-3 text-sm font-semibold text-white dark:bg-white dark:text-slate-900"
            >
              Back to Settings
            </button>
          )}
        </Card>
      </main>
    </div>
  )
}
