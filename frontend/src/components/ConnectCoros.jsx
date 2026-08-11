import { useState } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import { Watch } from 'lucide-react'
import { getCorosAuthUrl } from '../api/coros'
import { useAuth } from '../context/AuthContext'
import { pagePaddingClass, pageShellClass } from '../utils/statusColors'
import Navigation from './Navigation'
import Card from './ui/Card'

export default function ConnectCoros() {
  const navigate = useNavigate()
  const {
    isAuthenticated,
    needsOnboarding,
    needsStravaStep,
    profile,
    markCorosOnboardingDone,
  } = useAuth()
  const [connecting, setConnecting] = useState(false)
  const [error, setError] = useState('')

  if (!isAuthenticated) return <Navigate to="/signin" replace />
  if (needsOnboarding) return <Navigate to="/onboarding" replace />
  if (needsStravaStep) return <Navigate to="/connect-strava" replace />

  async function handleConnect() {
    setConnecting(true)
    setError('')
    try {
      const { authorization_url: url } = await getCorosAuthUrl()
      window.location.href = url
    } catch (err) {
      setError(err.message || 'Failed to start COROS authorization.')
      setConnecting(false)
    }
  }

  async function handleSkip() {
    await markCorosOnboardingDone()
    navigate('/dashboard')
  }

  return (
    <div className={pageShellClass}>
      <Navigation subtitle="Connect COROS" showProfileLink={false} />

      <main className={`${pagePaddingClass} flex min-h-[calc(100vh-80px)] items-center justify-center`}>
        <Card className="w-full max-w-lg p-10 text-center">
          <div className="mx-auto flex h-20 w-20 items-center justify-center rounded-full bg-slate-900/10 dark:bg-white/10">
            <Watch className="h-10 w-10 text-slate-900 dark:text-white" />
          </div>

          <h1 className="mt-6 text-3xl font-bold text-slate-900 dark:text-white">
            Connect COROS
          </h1>
          <p className="mt-3 text-slate-500 dark:text-slate-400">
            Sync sleep, HRV, stress, recovery, VO2max, training load, and your COROS schedule
            into one dashboard — ready for AI coaching later.
          </p>
          {profile?.coros_onboarding_done && (
            <p className="mt-2 text-sm text-sage">You can reconnect anytime from Settings.</p>
          )}

          <button
            type="button"
            onClick={handleConnect}
            disabled={connecting}
            className="mt-8 w-full rounded-2xl bg-slate-900 px-6 py-4 text-lg font-semibold text-white disabled:opacity-60 dark:bg-white dark:text-slate-900"
          >
            {connecting ? 'Redirecting...' : 'Connect with COROS'}
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
