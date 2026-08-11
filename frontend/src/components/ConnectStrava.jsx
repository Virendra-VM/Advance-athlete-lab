import { useState } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import { Activity } from 'lucide-react'
import { getStravaAuthUrl } from '../api/strava'
import { useAuth } from '../context/AuthContext'
import { pagePaddingClass, pageShellClass } from '../utils/statusColors'
import Navigation from './Navigation'
import Card from './ui/Card'

export default function ConnectStrava() {
  const navigate = useNavigate()
  const { isAuthenticated, needsOnboarding, needsStravaStep, profile, markStravaOnboardingDone } = useAuth()
  const [connecting, setConnecting] = useState(false)
  const [error, setError] = useState('')

  if (!isAuthenticated) return <Navigate to="/signin" replace />
  if (needsOnboarding) return <Navigate to="/onboarding" replace />
  if (!needsStravaStep) {
    return <Navigate to={profile?.coros_onboarding_done ? '/dashboard' : '/connect-coros'} replace />
  }

  async function handleConnect() {
    setConnecting(true)
    setError('')
    try {
      const { authorization_url: url } = await getStravaAuthUrl(profile?.id)
      window.location.href = url
    } catch (err) {
      setError(err.message || 'Failed to start Strava authorization.')
      setConnecting(false)
    }
  }

  async function handleSkip() {
    try {
      await markStravaOnboardingDone()
      navigate('/dashboard')
    } catch (err) {
      setError(err.message || 'Failed to continue. Please try again.')
    }
  }

  return (
    <div className={pageShellClass}>
      <Navigation subtitle="Connect Strava" showProfileLink={false} />

      <main className={`${pagePaddingClass} flex min-h-[calc(100vh-80px)] items-center justify-center`}>
        <Card className="w-full max-w-lg p-10 text-center">
          <div className="mx-auto flex h-20 w-20 items-center justify-center rounded-full bg-[#FC4C02]/10">
            <Activity className="h-10 w-10 text-[#FC4C02]" />
          </div>

          <h1 className="mt-6 text-3xl font-bold text-slate-900 dark:text-white">
            Connect your Strava
          </h1>
          <p className="mt-3 text-slate-500 dark:text-slate-400">
            Sync your activities and unlock training load insights, ACWR monitoring, and your full dashboard.
          </p>

          <button
            type="button"
            onClick={handleConnect}
            disabled={connecting}
            className="mt-8 w-full rounded-2xl bg-[#FC4C02] px-6 py-4 text-lg font-semibold text-white disabled:opacity-60"
          >
            {connecting ? 'Redirecting...' : 'Connect with Strava'}
          </button>

          <button
            type="button"
            onClick={handleSkip}
            className="mt-4 w-full text-sm text-slate-500 underline-offset-4 hover:underline dark:text-slate-400"
          >
            Skip for now — go to dashboard
          </button>

          {error && <p className="mt-4 text-sm text-danger-muted">{error}</p>}
        </Card>
      </main>
    </div>
  )
}
