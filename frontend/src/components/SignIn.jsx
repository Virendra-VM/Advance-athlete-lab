import { useState } from 'react'
import { Navigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { pageShellClass } from '../utils/statusColors'
import Card from './ui/Card'

export default function SignIn() {
  const { login, register, isAuthenticated, needsOnboarding, needsStravaStep } = useAuth()
  const [mode, setMode] = useState('signin')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [name, setName] = useState('')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  if (isAuthenticated) {
    if (needsOnboarding) return <Navigate to="/onboarding" replace />
    if (needsStravaStep) return <Navigate to="/connect-strava" replace />
    return <Navigate to="/dashboard" replace />
  }

  async function handleSubmit(event) {
    event.preventDefault()
    setError('')
    setSubmitting(true)
    try {
      if (mode === 'signin') {
        await login({ email, password })
      } else {
        await register({ email, password, name })
      }
    } catch (err) {
      setError(err.message || 'Something went wrong.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className={`${pageShellClass} flex min-h-screen items-center justify-center px-4`}>
      <Card className="w-full max-w-md p-8">
        <div className="mb-8 text-center">
          <p className="text-sm font-semibold uppercase tracking-widest text-sage">Advance Athlete Lab</p>
          <h1 className="mt-2 text-3xl font-bold text-slate-900 dark:text-white">
            {mode === 'signin' ? 'Welcome back' : 'Create your account'}
          </h1>
          <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">
            {mode === 'signin'
              ? 'Sign in to continue your training journey.'
              : 'Start building your personalized fitness plan.'}
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-5">
          {mode === 'signup' && (
            <div>
              <label className="mb-2 block text-sm font-medium text-slate-700 dark:text-slate-300">
                Full name
              </label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="w-full rounded-xl border border-slate-200 bg-white px-4 py-3 outline-none ring-sage focus:ring-2 dark:border-white/10 dark:bg-gray-900"
                required
              />
            </div>
          )}

          <div>
            <label className="mb-2 block text-sm font-medium text-slate-700 dark:text-slate-300">
              Email
            </label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full rounded-xl border border-slate-200 bg-white px-4 py-3 outline-none ring-sage focus:ring-2 dark:border-white/10 dark:bg-gray-900"
              required
            />
          </div>

          <div>
            <label className="mb-2 block text-sm font-medium text-slate-700 dark:text-slate-300">
              Password
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              minLength={8}
              className="w-full rounded-xl border border-slate-200 bg-white px-4 py-3 outline-none ring-sage focus:ring-2 dark:border-white/10 dark:bg-gray-900"
              required
            />
            {mode === 'signup' && (
              <p className="mt-1 text-xs text-slate-400">At least 8 characters</p>
            )}
          </div>

          {error && <p className="text-sm text-danger-muted">{error}</p>}

          <button
            type="submit"
            disabled={submitting}
            className="w-full rounded-xl bg-sage px-4 py-3 font-semibold text-white disabled:opacity-60"
          >
            {submitting ? 'Please wait...' : mode === 'signin' ? 'Sign In' : 'Create Account'}
          </button>
        </form>

        <p className="mt-6 text-center text-sm text-slate-500">
          {mode === 'signin' ? (
            <>
              New here?{' '}
              <button type="button" onClick={() => setMode('signup')} className="font-semibold text-sage">
                Create an account
              </button>
            </>
          ) : (
            <>
              Already have an account?{' '}
              <button type="button" onClick={() => setMode('signin')} className="font-semibold text-sage">
                Sign in
              </button>
            </>
          )}
        </p>
      </Card>
    </div>
  )
}
