import { useEffect, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { CheckCircle2, MailWarning } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import Card from '../components/ui/Card'
import Navigation from '../components/Navigation'
import { pagePaddingClass, pageShellClass } from '../utils/statusColors'

export default function VerifyEmailPage() {
  const [searchParams] = useSearchParams()
  const token = searchParams.get('token') || ''
  const { confirmEmail } = useAuth()
  const [state, setState] = useState(token ? 'pending' : 'missing')
  const [error, setError] = useState('')
  const attempted = useRef('')

  useEffect(() => {
    if (!token || attempted.current === token) return
    attempted.current = token
    confirmEmail(token)
      .then(() => setState('done'))
      .catch((err) => {
        setError(err.message || 'This verification link is invalid or has expired.')
        setState('failed')
      })
  }, [token, confirmEmail])

  const verified = state === 'done'

  return (
    <div className={pageShellClass}>
      <Navigation subtitle="Email verification" showProfileLink={false} />
      <main className={`${pagePaddingClass} flex min-h-[calc(100vh-80px)] items-center justify-center`}>
        <Card className="w-full max-w-lg p-10 text-center">
          <div
            className={`mx-auto flex h-16 w-16 items-center justify-center rounded-full ${
              verified ? 'bg-sage/10 text-sage' : 'bg-amber-status/10 text-amber-status'
            }`}
          >
            {verified ? (
              <CheckCircle2 className="h-8 w-8" />
            ) : (
              <MailWarning className="h-8 w-8" />
            )}
          </div>

          <h1 className="mt-6 text-2xl font-bold">
            {state === 'pending' && 'Verifying your email…'}
            {verified && 'Email verified'}
            {state === 'failed' && 'Link not valid'}
            {state === 'missing' && 'Nothing to verify'}
          </h1>
          <p className="mt-3 text-[var(--aal-muted)]">
            {state === 'pending' && 'One moment while we confirm your link.'}
            {verified && 'Thanks — account alerts and training summaries are now enabled.'}
            {state === 'failed' && (error || 'Request a fresh link from the banner in the app.')}
            {state === 'missing' && 'Open the link from your verification email to confirm your address.'}
          </p>

          <Link
            to="/dashboard"
            className="mt-8 inline-block rounded-xl bg-sage px-6 py-3 font-semibold text-white"
          >
            Go to dashboard
          </Link>
        </Card>
      </main>
    </div>
  )
}
