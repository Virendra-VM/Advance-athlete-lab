import { useState } from 'react'
import { MailWarning, X } from 'lucide-react'
import { useAuth } from '../context/AuthContext'

const DISMISS_KEY = 'aal_email_banner_dismissed'

export default function EmailVerifyBanner() {
  const { isAuthenticated, emailVerified, user, resendVerificationEmail } = useAuth()
  const [dismissed, setDismissed] = useState(
    () => sessionStorage.getItem(DISMISS_KEY) === '1',
  )
  const [status, setStatus] = useState('')
  const [sending, setSending] = useState(false)

  if (!isAuthenticated || emailVerified || dismissed) return null

  async function handleResend() {
    setSending(true)
    setStatus('')
    try {
      const result = await resendVerificationEmail()
      setStatus(
        result?.dev_verify_token
          ? `No mail transport configured. Dev link: /verify-email?token=${result.dev_verify_token}`
          : `Verification email sent to ${result?.email || user?.email}.`,
      )
    } catch (err) {
      setStatus(err.message || 'Could not send the verification email.')
    } finally {
      setSending(false)
    }
  }

  function handleDismiss() {
    sessionStorage.setItem(DISMISS_KEY, '1')
    setDismissed(true)
  }

  return (
    <div className="mb-6 flex flex-col gap-3 rounded-xl border border-amber-status/40 bg-amber-status/10 px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
      <div className="flex min-w-0 items-start gap-3">
        <MailWarning className="mt-0.5 h-4 w-4 shrink-0 text-amber-status" />
        <div className="min-w-0 text-sm">
          <p className="font-semibold">Verify your email</p>
          <p className="mt-0.5 text-[var(--aal-muted)]">
            {status || `Confirm ${user?.email} to get training summaries and account alerts. Everything keeps working until you do.`}
          </p>
        </div>
      </div>
      <div className="flex shrink-0 items-center gap-2">
        <button
          type="button"
          onClick={handleResend}
          disabled={sending}
          className="rounded-lg border border-[var(--aal-line)] bg-[var(--aal-card)] px-3 py-1.5 text-sm font-semibold disabled:opacity-60"
        >
          {sending ? 'Sending…' : 'Send link'}
        </button>
        <button
          type="button"
          onClick={handleDismiss}
          className="rounded-lg p-1.5 text-[var(--aal-muted)] hover:text-[var(--aal-ink)]"
          aria-label="Dismiss"
        >
          <X className="h-4 w-4" />
        </button>
      </div>
    </div>
  )
}
