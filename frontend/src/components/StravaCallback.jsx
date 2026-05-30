import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { completeStravaOAuth } from '../api/strava'
import { useAuth } from '../context/AuthContext'
import { pageShellClass } from '../utils/statusColors'
import Navigation from './Navigation'
import Card from './ui/Card'

export default function StravaCallback() {
  const navigate = useNavigate()
  const { isAuthenticated, refreshUser, markStravaOnboardingDone } = useAuth()
  const [status, setStatus] = useState('loading')
  const [message, setMessage] = useState('Connecting your Strava account...')

  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const error = params.get('error')
    const code = params.get('code')
    const state = params.get('state')

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

    let cancelled = false

    async function exchangeCode() {
      try {
        await completeStravaOAuth(code, state)
        if (cancelled) return
        if (isAuthenticated) {
          await refreshUser()
          await markStravaOnboardingDone()
        }
        setStatus('success')
        setMessage('Strava connected! Redirecting to dashboard...')
        setTimeout(() => navigate(isAuthenticated ? '/dashboard' : '/signin'), 2000)
      } catch (err) {
        if (cancelled) return
        setStatus('error')
        setMessage(err.message || 'Failed to connect Strava account.')
      }
    }

    exchangeCode()
    return () => {
      cancelled = true
    }
  }, [navigate, isAuthenticated, refreshUser, markStravaOnboardingDone])

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

