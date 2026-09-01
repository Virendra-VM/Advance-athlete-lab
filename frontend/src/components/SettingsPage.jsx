import { useCallback, useEffect, useRef, useState } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import {
  CheckCircle2,
  HardDrive,
  Link2,
  LogOut,
  RefreshCw,
  Upload,
  Watch,
  Wifi,
  WifiOff,
} from 'lucide-react'
import { dedupeActivities, getImportStatus, uploadStravaHistoryExport } from '../api/activities'
import {
  getCorosConnectionStatus,
  getCorosAuthUrl,
  getCorosCycleLatest,
  getCorosDevices,
  getCorosSyncStatus,
  startCorosSync,
  disconnectCoros,
  backfillCorosFit,
} from '../api/coros'
import { getStravaAuthUrl, getStravaConnectionStatus, startStravaSync, getStravaSyncStatus } from '../api/strava'
import { useAuth } from '../context/AuthContext'
import AppShell from './layout/AppShell'
import ThemeToggle from './ThemeToggle'
import PageHeader from './ui/PageHeader'
import SyncResultModal, { buildSyncResult } from './ui/SyncResultModal'
import { useTheme } from '../context/ThemeProvider'
import OnboardingField, { ConsentsField } from './onboarding/OnboardingFields'
import { BLOOD_TYPES } from '../utils/onboardingSteps'

function StatusPill({ connected, loading, label }) {
  if (loading) {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full border border-[var(--aal-line)] bg-[var(--aal-bg)] px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--aal-muted)]">
        Checking…
      </span>
    )
  }
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.14em] ${
        connected
          ? 'bg-[var(--aal-accent-soft)] text-sage'
          : 'border border-[var(--aal-line)] bg-[var(--aal-bg)] text-[var(--aal-muted)]'
      }`}
    >
      {connected ? <Wifi className="h-3 w-3" /> : <WifiOff className="h-3 w-3" />}
      {label}
    </span>
  )
}

function ActionButton({ children, onClick, disabled, variant = 'secondary', className = '' }) {
  const styles = {
    primary:
      'bg-[var(--aal-ink)] text-[var(--aal-card)] hover:opacity-90',
    secondary:
      'border border-[var(--aal-line)] bg-[var(--aal-card)] text-[var(--aal-ink)] hover:bg-[var(--aal-bg)]',
    strava: 'bg-[#FC4C02] text-white hover:brightness-110',
    danger:
      'border border-danger-muted/35 bg-transparent text-danger-muted hover:bg-danger-muted/5',
  }
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={`inline-flex items-center justify-center gap-2 rounded-xl px-4 py-2.5 text-sm font-semibold transition disabled:cursor-not-allowed disabled:opacity-55 ${styles[variant]} ${className}`}
    >
      {children}
    </button>
  )
}

export default function SettingsPage() {
  const { isAuthenticated, profile, user, emailVerified, resendVerificationEmail, updateProfile, logout } =
    useAuth()
  const { theme } = useTheme()
  const location = useLocation()
  const [verifySending, setVerifySending] = useState(false)
  const [verifyMessage, setVerifyMessage] = useState('')
  const [stravaConnected, setStravaConnected] = useState(false)
  const [stravaAthleteId, setStravaAthleteId] = useState(null)
  const [stravaLoading, setStravaLoading] = useState(true)
  const [stravaConnecting, setStravaConnecting] = useState(false)
  const [stravaSyncing, setStravaSyncing] = useState(false)
  const [stravaError, setStravaError] = useState('')
  const [corosConnected, setCorosConnected] = useState(false)
  const [syncResult, setSyncResult] = useState(null)
  const [corosLoading, setCorosLoading] = useState(true)
  const [corosConnecting, setCorosConnecting] = useState(false)
  const [corosSyncing, setCorosSyncing] = useState(false)
  const [corosFitBackfilling, setCorosFitBackfilling] = useState(false)
  const [corosError, setCorosError] = useState('')
  const [corosFitMessage, setCorosFitMessage] = useState('')
  const [corosLastSynced, setCorosLastSynced] = useState(null)
  const [devices, setDevices] = useState([])
  const [cycle, setCycle] = useState(null)
  const [showCycle, setShowCycle] = useState(
    () => localStorage.getItem('aal_show_cycle') === '1',
  )
  const [dedupeRunning, setDedupeRunning] = useState(false)
  const [dedupeMessage, setDedupeMessage] = useState('')
  const [importRunning, setImportRunning] = useState(false)
  const [importStatus, setImportStatus] = useState(null)
  const [importError, setImportError] = useState('')
  const [uploading, setUploading] = useState(false)
  const wasImportRunning = useRef(false)
  const uploadInputRef = useRef(null)
  const [consentOverride, setConsentOverride] = useState(undefined)
  const [bloodOverride, setBloodOverride] = useState(undefined)
  const [privacySaving, setPrivacySaving] = useState(false)
  const [privacyMessage, setPrivacyMessage] = useState('')
  const [privacyError, setPrivacyError] = useState('')
  const [privacyTarget, setPrivacyTarget] = useState(null)

  const consents =
    consentOverride ?? profile?.consents ?? { ai_coaching: false, health_data: false, research: false }
  const bloodType = bloodOverride !== undefined ? bloodOverride : (profile?.blood_type ?? null)

  const loadStravaStatus = useCallback(async () => {
    if (!profile?.id) return
    setStravaLoading(true)
    setStravaError('')
    try {
      const status = await getStravaConnectionStatus()
      setStravaConnected(status.connected)
      setStravaAthleteId(status.strava_athlete_id)
    } catch (err) {
      setStravaError(err.message || 'Failed to load Strava connection status.')
    } finally {
      setStravaLoading(false)
    }
  }, [profile?.id])

  const loadCorosExtras = useCallback(async () => {
    try {
      const [deviceRows, cycleLatest] = await Promise.all([
        getCorosDevices().catch(() => []),
        getCorosCycleLatest().catch(() => null),
      ])
      setDevices(deviceRows || [])
      setCycle(cycleLatest)
    } catch {
      setDevices([])
      setCycle(null)
    }
  }, [])

  const loadCorosStatus = useCallback(async () => {
    setCorosLoading(true)
    setCorosError('')
    try {
      const status = await getCorosConnectionStatus()
      setCorosConnected(status.connected)
      setCorosLastSynced(status.last_synced_at)
      if (status.connected) await loadCorosExtras()
    } catch (err) {
      setCorosError(err.message || 'Failed to load COROS connection status.')
    } finally {
      setCorosLoading(false)
    }
  }, [loadCorosExtras])

  const pollImportStatus = useCallback(async () => {
    try {
      const status = await getImportStatus()
      setImportStatus(status)
      setImportRunning(status.running)
      wasImportRunning.current = status.running
    } catch (err) {
      setImportError(err.message || 'Failed to load import status.')
    }
  }, [])

  useEffect(() => {
    loadStravaStatus()
  }, [loadStravaStatus])

  useEffect(() => {
    loadCorosStatus()
  }, [loadCorosStatus])

  useEffect(() => {
    pollImportStatus()
    const intervalId = window.setInterval(pollImportStatus, 2000)
    return () => window.clearInterval(intervalId)
  }, [pollImportStatus])

  useEffect(() => {
    const id = (location.hash || '').replace(/^#/, '')
    if (!id) return
    window.setTimeout(() => {
      document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }, 80)
  }, [location.hash])

  if (!isAuthenticated) return <Navigate to="/signin" replace />

  async function handleResendVerification() {
    setVerifySending(true)
    setVerifyMessage('')
    try {
      const result = await resendVerificationEmail()
      setVerifyMessage(
        result?.dev_verify_token
          ? `No mail transport configured. Dev link: /verify-email?token=${result.dev_verify_token}`
          : 'Verification email sent. Check your inbox.',
      )
    } catch (err) {
      setVerifyMessage(err.message || 'Could not send the verification email.')
    } finally {
      setVerifySending(false)
    }
  }

  async function handleConnectStrava() {
    setStravaConnecting(true)
    setStravaError('')
    try {
      const { authorization_url: authorizationUrl } = await getStravaAuthUrl()
      window.location.href = authorizationUrl
    } catch (err) {
      setStravaError(err.message || 'Failed to start Strava authorization.')
      setStravaConnecting(false)
    }
  }

  async function handleSyncStrava() {
    if (!profile?.id) return
    setStravaSyncing(true)
    setStravaError('')
    try {
      await startStravaSync()
      let status = null
      const started = Date.now()
      while (Date.now() - started < 120000) {
        await new Promise((resolve) => setTimeout(resolve, 1200))
        status = await getStravaSyncStatus()
        if (!status.running) break
      }
      try {
        await dedupeActivities()
      } catch {
        // non-fatal
      }
      setSyncResult(buildSyncResult('strava', status || {}))
    } catch (err) {
      setStravaError(err.message || 'Failed to sync Strava.')
    } finally {
      setStravaSyncing(false)
    }
  }

  async function handleConnectCoros() {
    setCorosConnecting(true)
    setCorosError('')
    try {
      const { authorization_url: authorizationUrl } = await getCorosAuthUrl()
      window.location.href = authorizationUrl
    } catch (err) {
      setCorosError(err.message || 'Failed to start COROS authorization.')
      setCorosConnecting(false)
    }
  }

  async function handleSyncCoros() {
    setCorosSyncing(true)
    setCorosError('')
    try {
      await startCorosSync()
      let status = null
      const started = Date.now()
      while (Date.now() - started < 120000) {
        await new Promise((resolve) => setTimeout(resolve, 1200))
        status = await getCorosSyncStatus()
        if (!status.running) break
      }
      try {
        await dedupeActivities()
      } catch {
        // Non-fatal
      }
      await loadCorosStatus()
      setSyncResult(buildSyncResult('coros', status || {}))
    } catch (err) {
      setCorosError(err.message || 'Failed to sync COROS.')
    } finally {
      setCorosSyncing(false)
    }
  }

  async function handleBackfillCorosFit() {
    setCorosFitBackfilling(true)
    setCorosError('')
    setCorosFitMessage('')
    try {
      const result = await backfillCorosFit(15)
      if (result?.reason === 'quota_exhausted') {
        setCorosFitMessage('COROS FIT daily quota reached. Try again tomorrow.')
      } else {
        setCorosFitMessage(
          `Filled ${result?.filled ?? 0} of ${result?.attempted ?? 0} · ${result?.remaining_quota ?? '—'} left today`,
        )
      }
    } catch (err) {
      setCorosError(err.message || 'Failed to backfill COROS FIT streams.')
    } finally {
      setCorosFitBackfilling(false)
    }
  }

  async function handleDisconnectCoros() {
    setCorosError('')
    try {
      await disconnectCoros()
      setDevices([])
      setCycle(null)
      await loadCorosStatus()
    } catch (err) {
      setCorosError(err.message || 'Failed to disconnect COROS.')
    }
  }

  function toggleCycleVisibility() {
    const next = !showCycle
    setShowCycle(next)
    localStorage.setItem('aal_show_cycle', next ? '1' : '0')
  }

  async function handleMergeDuplicates() {
    setDedupeRunning(true)
    setDedupeMessage('')
    try {
      const result = await dedupeActivities()
      const linked = result?.linked ?? 0
      setDedupeMessage(
        linked > 0
          ? `Merged ${linked} duplicate workout${linked === 1 ? '' : 's'}. Strava keeps the visible copy; COROS twin is hidden.`
          : 'No new duplicates found — everything already looks linked.',
      )
      if (linked > 0) {
        setSyncResult({
          title: 'Duplicates merged',
          message:
            linked === 1
              ? '1 COROS/Strava pair was the same workout. The Strava copy stays visible (with streams); the COROS twin is hidden from lists.'
              : `${linked} COROS/Strava pairs were the same workouts. Strava copies stay visible; COROS twins are hidden from lists.`,
          details: [`${linked} pair${linked === 1 ? '' : 's'} linked`],
        })
      }
    } catch (err) {
      setDedupeMessage(err.message || 'Failed to merge duplicates.')
    } finally {
      setDedupeRunning(false)
    }
  }

  async function handleUploadClick() {
    if (importRunning || uploading) return
    uploadInputRef.current?.click()
  }

  async function handleUploadSelected(event) {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (!file) return

    setImportError('')
    setUploading(true)
    wasImportRunning.current = true
    try {
      await uploadStravaHistoryExport(profile.id, file)
      await pollImportStatus()
    } catch (err) {
      setImportError(err.message || 'Failed to upload Strava export.')
      wasImportRunning.current = false
    } finally {
      setUploading(false)
    }
  }

  async function savePrivacy(payload, target) {
    setPrivacyTarget(target)
    setPrivacySaving(true)
    setPrivacyError('')
    setPrivacyMessage('')
    try {
      await updateProfile(payload)
      setPrivacyMessage('Saved.')
    } catch (err) {
      setPrivacyError(err.message || 'Could not save.')
    } finally {
      setPrivacySaving(false)
    }
  }

  async function handleConsentsChange(value) {
    const next = {
      ai_coaching: Boolean(value?.ai_coaching),
      health_data: Boolean(value?.health_data),
      research: Boolean(value?.research),
    }
    setConsentOverride(next)
    await savePrivacy({ consents: next }, 'consents')
  }

  async function handleBloodTypeChange(value) {
    setBloodOverride(value)
    await savePrivacy({ blood_type: value || null }, 'blood')
  }

  const importPct =
    importRunning && importStatus?.total > 0
      ? Math.min(100, Math.round((importStatus.processed / importStatus.total) * 100))
      : 0

  if (!profile) {
    return (
      <AppShell title="Settings">
        <p className="text-sm text-[var(--aal-muted)]">Loading...</p>
      </AppShell>
    )
  }

  return (
    <AppShell title="Settings">
      <div className="w-full space-y-10">
        <PageHeader
          eyebrow="Account"
          title="Settings"
          subtitle="Integrations, privacy, appearance, and the rest of your account."
        />

        {/* Appearance */}
        <section className="space-y-4">
          <div>
            <h2 className="text-lg font-semibold">Appearance</h2>
            <p className="mt-0.5 text-sm text-[var(--aal-muted)]">
              Switch between light and dark mode for the whole app.
            </p>
          </div>
          <div className="rounded-2xl border border-[var(--aal-line)] bg-[var(--aal-card)] p-5 sm:p-6">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <h3 className="text-base font-semibold">Theme</h3>
                <p className="mt-1 text-sm text-[var(--aal-muted)]">
                  Currently using {theme === 'dark' ? 'dark' : 'light'} mode.
                </p>
              </div>
              <div className="flex items-center gap-3">
                <span className="text-sm text-[var(--aal-muted)]">
                  {theme === 'dark' ? 'Dark' : 'Light'}
                </span>
                <ThemeToggle />
              </div>
            </div>
          </div>
        </section>

        {/* Email verification */}
        <section className="space-y-4">
          <div>
            <h2 className="text-lg font-semibold">Email</h2>
            <p className="mt-0.5 text-sm text-[var(--aal-muted)]">
              Verification is optional — the app works either way.
            </p>
          </div>
          <div className="rounded-2xl border border-[var(--aal-line)] bg-[var(--aal-card)] p-5 sm:p-6">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <h3 className="text-base font-semibold">{user?.email || '—'}</h3>
                  <StatusPill
                    connected={emailVerified}
                    label={emailVerified ? 'Verified' : 'Unverified'}
                  />
                </div>
                <p className="mt-1 text-sm text-[var(--aal-muted)]">
                  {verifyMessage ||
                    (emailVerified
                      ? 'Account alerts and training summaries are enabled.'
                      : 'Verify to receive account alerts and weekly training summaries.')}
                </p>
              </div>
              {!emailVerified && (
                <ActionButton
                  onClick={handleResendVerification}
                  disabled={verifySending}
                  variant="secondary"
                >
                  {verifySending ? 'Sending…' : 'Send verification link'}
                </ActionButton>
              )}
            </div>
          </div>
        </section>

        {/* Privacy */}
        <section id="privacy" className="scroll-mt-24 space-y-4">
          <div>
            <h2 className="text-lg font-semibold">Privacy</h2>
            <p className="mt-0.5 text-sm text-[var(--aal-muted)]">
              Coaching guidance only — not medical advice. Changes save as you toggle them.
            </p>
          </div>
          <div className="rounded-2xl border border-[var(--aal-line)] bg-[var(--aal-card)] p-5 sm:p-6">
            <ConsentsField value={consents} onChange={handleConsentsChange} />
            {privacyTarget === 'consents' && privacySaving ? (
              <p className="mt-3 text-sm text-[var(--aal-muted)]">Saving…</p>
            ) : privacyTarget === 'consents' && privacyError ? (
              <p className="mt-3 text-sm text-danger-muted">{privacyError}</p>
            ) : privacyTarget === 'consents' && privacyMessage ? (
              <p className="mt-3 text-sm text-sage">{privacyMessage}</p>
            ) : null}
          </div>
        </section>

        {/* Health record */}
        <section id="health-record" className="scroll-mt-24 space-y-4">
          <div>
            <h2 className="text-lg font-semibold">Health record</h2>
            <p className="mt-0.5 text-sm text-[var(--aal-muted)]">
              Optional and never used in coaching prompts.
            </p>
          </div>
          <div className="rounded-2xl border border-[var(--aal-line)] bg-[var(--aal-card)] p-5 sm:p-6">
            <OnboardingField
              field={{
                key: 'blood_type',
                label: 'Blood type',
                type: 'chips-single',
                options: BLOOD_TYPES,
                help: 'Stored for emergencies only.',
              }}
              answers={{ blood_type: bloodType }}
              value={bloodType}
              onChange={handleBloodTypeChange}
            />
            {privacyTarget === 'blood' && privacySaving ? (
              <p className="mt-3 text-sm text-[var(--aal-muted)]">Saving…</p>
            ) : privacyTarget === 'blood' && privacyError ? (
              <p className="mt-3 text-sm text-danger-muted">{privacyError}</p>
            ) : privacyTarget === 'blood' && privacyMessage ? (
              <p className="mt-3 text-sm text-sage">{privacyMessage}</p>
            ) : null}
          </div>
        </section>

        {/* Integrations */}
        <section className="space-y-4">
          <div>
            <h2 className="text-lg font-semibold">Integrations</h2>
            <p className="mt-0.5 text-sm text-[var(--aal-muted)]">
              Connect sources and keep activity + health data in sync.
            </p>
          </div>

          <div className="overflow-hidden rounded-2xl border border-[var(--aal-line)] bg-[var(--aal-card)]">
            {/* Strava row */}
            <div className="border-b border-[var(--aal-line)] p-5 sm:p-6">
              <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
                <div className="flex min-w-0 items-start gap-3">
                  <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-[#FC4C02]/12 text-[#FC4C02]">
                    <Link2 className="h-5 w-5" />
                  </div>
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <h3 className="text-base font-semibold">Strava</h3>
                      <StatusPill
                        loading={stravaLoading}
                        connected={stravaConnected}
                        label={stravaConnected ? 'Live' : 'Off'}
                      />
                    </div>
                    <p className="mt-1 text-sm text-[var(--aal-muted)]">
                      Activities, GPS, and HR streams
                      {stravaConnected ? ` · Athlete #${stravaAthleteId}` : ''}
                    </p>
                  </div>
                </div>
                <div className="flex flex-wrap gap-2 lg:justify-end">
                  {stravaConnected ? (
                    <ActionButton
                      onClick={handleSyncStrava}
                      disabled={stravaSyncing}
                      variant="secondary"
                    >
                      <RefreshCw className={`h-4 w-4 ${stravaSyncing ? 'sync-spin' : ''}`} />
                      {stravaSyncing ? 'Syncing…' : 'Sync now'}
                    </ActionButton>
                  ) : null}
                  <ActionButton
                    onClick={handleConnectStrava}
                    disabled={stravaConnecting || stravaConnected}
                    variant="strava"
                  >
                    {stravaConnecting
                      ? 'Redirecting…'
                      : stravaConnected
                        ? 'Connected'
                        : 'Connect Strava'}
                  </ActionButton>
                </div>
              </div>
              {stravaError && (
                <p className="mt-3 text-sm text-danger-muted">{stravaError}</p>
              )}
            </div>

            {/* COROS row */}
            <div className="p-5 sm:p-6">
              <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
                <div className="flex min-w-0 items-start gap-3">
                  <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-[var(--aal-accent-soft)] text-sage">
                    <Watch className="h-5 w-5" />
                  </div>
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <h3 className="text-base font-semibold">COROS</h3>
                      <StatusPill
                        loading={corosLoading}
                        connected={corosConnected}
                        label={corosConnected ? 'Live' : 'Off'}
                      />
                    </div>
                    <p className="mt-1 text-sm text-[var(--aal-muted)]">
                      Sleep, HRV, recovery, VO2, and schedule
                      {corosLastSynced
                        ? ` · Last synced ${new Date(corosLastSynced).toLocaleString()}`
                        : ''}
                    </p>
                  </div>
                </div>
                <div className="flex flex-wrap gap-2 lg:justify-end">
                  {corosConnected && (
                    <>
                      <ActionButton
                        onClick={handleSyncCoros}
                        disabled={corosSyncing}
                        variant="secondary"
                      >
                        <RefreshCw className={`h-4 w-4 ${corosSyncing ? 'sync-spin' : ''}`} />
                        {corosSyncing ? 'Syncing…' : 'Sync now'}
                      </ActionButton>
                      <ActionButton
                        onClick={handleBackfillCorosFit}
                        disabled={corosFitBackfilling || corosSyncing}
                        variant="secondary"
                      >
                        {corosFitBackfilling ? 'Loading FIT…' : 'Backfill FIT'}
                      </ActionButton>
                      <ActionButton onClick={handleDisconnectCoros} variant="danger">
                        Disconnect
                      </ActionButton>
                    </>
                  )}
                  <ActionButton
                    onClick={handleConnectCoros}
                    disabled={corosConnecting}
                    variant="primary"
                  >
                    {corosConnecting
                      ? 'Redirecting…'
                      : corosConnected
                        ? 'Reconnect'
                        : 'Connect COROS'}
                  </ActionButton>
                </div>
              </div>
              {corosError && (
                <p className="mt-3 text-sm text-danger-muted">{corosError}</p>
              )}
              {corosFitMessage && (
                <p className="mt-3 flex items-center gap-1.5 text-sm text-sage">
                  <CheckCircle2 className="h-4 w-4 shrink-0" />
                  {corosFitMessage}
                </p>
              )}
            </div>
          </div>
        </section>

        {/* Devices */}
        {corosConnected && (
          <section className="space-y-4">
            <div>
              <h2 className="text-lg font-semibold">Devices</h2>
              <p className="mt-0.5 text-sm text-[var(--aal-muted)]">
                Watches and sensors synced from COROS.
              </p>
            </div>

            {devices.length === 0 ? (
              <div className="flex min-h-[140px] flex-col items-center justify-center rounded-2xl border border-dashed border-[var(--aal-line)] bg-[var(--aal-card)] px-6 text-center">
                <HardDrive className="mb-3 h-8 w-8 text-[var(--aal-muted)]" />
                <p className="text-sm font-medium">No devices yet</p>
                <p className="mt-1 text-sm text-[var(--aal-muted)]">
                  Run Sync now on COROS to pull your device list.
                </p>
              </div>
            ) : (
              <div className="overflow-hidden rounded-2xl border border-[var(--aal-line)] bg-[var(--aal-card)]">
                <ul className="divide-y divide-[var(--aal-line)]">
                  {devices.map((device) => (
                    <li
                      key={device.device_id || device.name}
                      className="flex flex-col gap-2 px-5 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-6"
                    >
                      <div className="flex min-w-0 items-center gap-3">
                        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-[var(--aal-accent-soft)] text-sage">
                          <Watch className="h-4 w-4" />
                        </div>
                        <div className="min-w-0">
                          <p className="truncate font-semibold">
                            {device.name || 'COROS device'}
                          </p>
                          <p className="truncate text-sm text-[var(--aal-muted)]">
                            {device.device_id ? `ID ${device.device_id}` : 'No device ID'}
                          </p>
                        </div>
                      </div>
                      <p className="text-sm text-[var(--aal-muted)] sm:text-right">
                        Firmware {device.firmware || '—'}
                      </p>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </section>
        )}

        {/* Cycle tracking */}
        {corosConnected && (
          <section className="space-y-4">
            <div className="flex flex-wrap items-end justify-between gap-3">
              <div>
                <h2 className="text-lg font-semibold">Cycle tracking</h2>
                <p className="mt-0.5 text-sm text-[var(--aal-muted)]">
                  Optional COROS menstrual cycle snapshot. Hidden by default.
                </p>
              </div>
              <ActionButton
                onClick={toggleCycleVisibility}
                variant="secondary"
                className="!px-3 !py-1.5 text-xs"
              >
                {showCycle ? 'Hide' : 'Show'}
              </ActionButton>
            </div>

            <div className="rounded-2xl border border-[var(--aal-line)] bg-[var(--aal-card)] p-5 sm:p-6">
              {!showCycle ? (
                <p className="text-sm text-[var(--aal-muted)]">
                  Opt in to view the latest cycle snapshot synced from COROS.
                </p>
              ) : !cycle?.available ? (
                <p className="text-sm text-[var(--aal-muted)]">
                  No cycle data available for this account.
                </p>
              ) : (
                <div className="space-y-3">
                  <p className="text-sm text-[var(--aal-muted)]">
                    Snapshot:{' '}
                    {cycle.snapshot_at
                      ? new Date(cycle.snapshot_at).toLocaleString()
                      : '—'}
                  </p>
                  <pre className="max-h-64 overflow-auto rounded-xl bg-[var(--aal-bg)] p-3 text-xs leading-relaxed">
                    {typeof cycle.data === 'string'
                      ? cycle.data
                      : JSON.stringify(cycle.data, null, 2)}
                  </pre>
                </div>
              )}
            </div>
          </section>
        )}

        {/* Data cleanup */}
        <section className="space-y-4">
          <div>
            <h2 className="text-lg font-semibold">Data cleanup</h2>
            <p className="mt-0.5 text-sm text-[var(--aal-muted)]">
              Merge workouts that arrived twice from COROS and Strava.
            </p>
          </div>
          <div className="rounded-2xl border border-[var(--aal-line)] bg-[var(--aal-card)] p-5 sm:p-6">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
              <div>
                <h3 className="text-base font-semibold">Merge duplicate activities</h3>
                <p className="mt-1 text-sm text-[var(--aal-muted)]">
                  Same workout from both apps (UTC vs local time) is linked so only one card
                  shows in Activities and Schedule.
                </p>
              </div>
              <ActionButton
                onClick={handleMergeDuplicates}
                disabled={dedupeRunning}
                variant="primary"
              >
                <RefreshCw className={`h-4 w-4 ${dedupeRunning ? 'sync-spin' : ''}`} />
                {dedupeRunning ? 'Merging…' : 'Merge duplicates now'}
              </ActionButton>
            </div>
            {dedupeMessage ? (
              <p className="mt-3 text-sm text-sage">{dedupeMessage}</p>
            ) : null}
          </div>
        </section>

        {/* Historical import */}
        <section className="space-y-4">
          <div>
            <h2 className="text-lg font-semibold">Historical import</h2>
            <p className="mt-0.5 text-sm text-[var(--aal-muted)]">
              Backfill past Strava activities from a bulk export zip.
            </p>
          </div>

          <div className="rounded-2xl border border-[var(--aal-line)] bg-[var(--aal-card)] p-5 sm:p-6">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
              <div className="flex min-w-0 items-start gap-3">
                <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-recovery/15 text-recovery">
                  <Upload className="h-5 w-5" />
                </div>
                <div>
                  <h3 className="text-base font-semibold">Strava bulk export</h3>
                  <p className="mt-1 text-sm text-[var(--aal-muted)]">
                    Download your archive from Strava, then upload the zip here to import
                    older activities into Advance Athlete Lab.
                  </p>
                </div>
              </div>
              <div className="shrink-0">
                <input
                  ref={uploadInputRef}
                  type="file"
                  accept=".zip,application/zip"
                  className="hidden"
                  onChange={handleUploadSelected}
                />
                <ActionButton
                  onClick={handleUploadClick}
                  disabled={importRunning || uploading}
                  variant="primary"
                >
                  <Upload className="h-4 w-4" />
                  {uploading
                    ? 'Uploading…'
                    : importRunning
                      ? 'Importing…'
                      : 'Upload Strava export'}
                </ActionButton>
              </div>
            </div>

            <div className="mt-5 grid gap-3 sm:grid-cols-3">
              <div className="rounded-xl border border-[var(--aal-line)] bg-[var(--aal-bg)]/50 p-3">
                <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[var(--aal-muted)]">
                  Imported
                </p>
                <p className="mt-1 text-xl font-semibold tabular-nums">
                  {importStatus?.imported ?? 0}
                </p>
              </div>
              <div className="rounded-xl border border-[var(--aal-line)] bg-[var(--aal-bg)]/50 p-3">
                <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[var(--aal-muted)]">
                  Skipped
                </p>
                <p className="mt-1 text-xl font-semibold tabular-nums">
                  {importStatus?.skipped ?? 0}
                </p>
              </div>
              <div className="rounded-xl border border-[var(--aal-line)] bg-[var(--aal-bg)]/50 p-3">
                <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[var(--aal-muted)]">
                  Total
                </p>
                <p className="mt-1 text-xl font-semibold tabular-nums">
                  {importStatus?.total ?? 0}
                </p>
              </div>
            </div>

            <div className="mt-4">
              <div className="mb-1.5 flex items-center justify-between text-xs text-[var(--aal-muted)]">
                <span>
                  {uploading
                    ? 'Uploading zip…'
                    : importRunning
                      ? `Processing ${importStatus?.processed ?? 0} / ${importStatus?.total ?? 0}`
                      : 'Ready for next upload'}
                </span>
                {importRunning && importStatus?.total > 0 ? (
                  <span className="font-medium tabular-nums">{importPct}%</span>
                ) : null}
              </div>
              <div className="h-2 overflow-hidden rounded-full bg-[var(--aal-line)]">
                <div
                  className="h-full rounded-full bg-sage transition-all duration-500"
                  style={{
                    width: `${importRunning && importStatus?.total > 0 ? importPct : uploading ? 12 : 0}%`,
                  }}
                />
              </div>
            </div>

            {importError && (
              <p className="mt-4 text-sm text-danger-muted">{importError}</p>
            )}
          </div>
        </section>

        {/* Session */}
        <section id="session" className="scroll-mt-24 space-y-4">
          <div>
            <h2 className="text-lg font-semibold">Session</h2>
            <p className="mt-0.5 text-sm text-[var(--aal-muted)]">
              Sign out of this browser. Your training data stays on the account.
            </p>
          </div>
          <div className="rounded-2xl border border-[var(--aal-line)] bg-[var(--aal-card)] p-5 sm:p-6">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <h3 className="text-base font-semibold">Log out</h3>
                <p className="mt-1 text-sm text-[var(--aal-muted)]">
                  Signed in as {user?.email || 'this account'}.
                </p>
              </div>
              <ActionButton onClick={logout} variant="danger">
                <LogOut className="h-4 w-4" />
                Log out
              </ActionButton>
            </div>
          </div>
        </section>
      </div>

      <SyncResultModal
        open={Boolean(syncResult)}
        onClose={() => setSyncResult(null)}
        title={syncResult?.title}
        message={syncResult?.message}
        details={syncResult?.details}
      />
    </AppShell>
  )
}
