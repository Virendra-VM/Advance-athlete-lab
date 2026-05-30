import { useCallback, useEffect, useRef, useState } from 'react'
import { Navigate } from 'react-router-dom'
import { CheckCircle2, Link2, Upload } from 'lucide-react'
import { getImportStatus, uploadStravaHistoryExport } from '../api/activities'
import { getStravaAuthUrl, getStravaConnectionStatus } from '../api/strava'
import { useAuth } from '../context/AuthContext'
import { pagePaddingClass, pageShellClass } from '../utils/statusColors'
import Navigation from './Navigation'
import Card from './ui/Card'

export default function SettingsPage() {
  const { isAuthenticated, profile } = useAuth()
  const [stravaConnected, setStravaConnected] = useState(false)
  const [stravaAthleteId, setStravaAthleteId] = useState(null)
  const [stravaLoading, setStravaLoading] = useState(true)
  const [stravaConnecting, setStravaConnecting] = useState(false)
  const [stravaError, setStravaError] = useState('')
  const [importRunning, setImportRunning] = useState(false)
  const [importStatus, setImportStatus] = useState(null)
  const [importError, setImportError] = useState('')
  const [uploading, setUploading] = useState(false)
  const wasImportRunning = useRef(false)
  const uploadInputRef = useRef(null)

  const loadStravaStatus = useCallback(async () => {
    if (!profile?.id) return
    setStravaLoading(true)
    setStravaError('')
    try {
      const status = await getStravaConnectionStatus(profile.id)
      setStravaConnected(status.connected)
      setStravaAthleteId(status.strava_athlete_id)
    } catch (err) {
      setStravaError(err.message || 'Failed to load Strava connection status.')
    } finally {
      setStravaLoading(false)
    }
  }, [profile?.id])

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
    pollImportStatus()
    const intervalId = window.setInterval(pollImportStatus, 2000)
    return () => window.clearInterval(intervalId)
  }, [pollImportStatus])

  if (!isAuthenticated) return <Navigate to="/signin" replace />
  if (!profile) {
    return (
      <div className={pageShellClass}>
        <Navigation subtitle="Settings" />
        <main className={pagePaddingClass}>Loading...</main>
      </div>
    )
  }

  async function handleConnectStrava() {
    setStravaConnecting(true)
    setStravaError('')
    try {
      const { authorization_url: authorizationUrl } = await getStravaAuthUrl(profile.id)
      window.location.href = authorizationUrl
    } catch (err) {
      setStravaError(err.message || 'Failed to start Strava authorization.')
      setStravaConnecting(false)
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

  return (
    <div className={pageShellClass}>
      <Navigation subtitle="Settings" />

      <main className={`${pagePaddingClass} mx-auto max-w-3xl space-y-6`}>
        <Card className="p-6">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <div className="flex items-center gap-2">
                <Link2 className="h-5 w-5 text-sage" />
                <h2 className="text-xl font-semibold text-slate-900 dark:text-white">Integrations</h2>
              </div>
              {stravaLoading ? (
                <p className="mt-2 text-sm text-slate-400">Checking Strava connection...</p>
              ) : stravaConnected ? (
                <p className="mt-2 flex items-center gap-1.5 text-sm text-sage">
                  <CheckCircle2 className="h-4 w-4" />
                  Connected to Strava athlete #{stravaAthleteId}
                </p>
              ) : (
                <p className="mt-2 text-sm text-slate-400">Not connected to Strava</p>
              )}
            </div>
            <button
              type="button"
              onClick={handleConnectStrava}
              disabled={stravaConnecting || stravaConnected}
              className="rounded-xl bg-[#FC4C02] px-5 py-3 font-semibold text-white disabled:cursor-not-allowed disabled:opacity-60"
            >
              {stravaConnecting ? 'Redirecting...' : stravaConnected ? 'Strava Connected' : 'Connect to Strava'}
            </button>
          </div>
          {stravaError && <p className="mt-4 text-sm text-danger-muted">{stravaError}</p>}
        </Card>

        <Card className="p-6">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <div className="flex items-center gap-2">
                <Upload className="h-5 w-5 text-recovery" />
                <h2 className="text-xl font-semibold text-slate-900 dark:text-white">Historical Import</h2>
              </div>
              <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">
                Upload your Strava bulk export zip to import past activities.
              </p>
              {importStatus && (
                <p className="mt-2 text-sm text-slate-400">
                  {uploading
                    ? 'Uploading zip file...'
                    : importRunning
                      ? `Processing ${importStatus.processed} / ${importStatus.total} files...`
                      : `Last run: imported ${importStatus.imported}, skipped ${importStatus.skipped}`}
                </p>
              )}
            </div>
            <div>
              <input
                ref={uploadInputRef}
                type="file"
                accept=".zip,application/zip"
                className="hidden"
                onChange={handleUploadSelected}
              />
              <button
                type="button"
                onClick={handleUploadClick}
                disabled={importRunning || uploading}
                className="rounded-xl border border-slate-200 px-5 py-3 text-sm font-semibold text-slate-700 disabled:cursor-not-allowed disabled:opacity-60 dark:border-white/10 dark:text-slate-300"
              >
                {uploading ? 'Uploading...' : importRunning ? 'Importing...' : 'Upload Strava Export'}
              </button>
            </div>
          </div>

          {importRunning && importStatus?.total > 0 && (
            <div className="mt-4 h-2 overflow-hidden rounded-full bg-slate-100 dark:bg-gray-700">
              <div
                className="h-full bg-sage transition-all"
                style={{
                  width: `${Math.min(100, Math.round((importStatus.processed / importStatus.total) * 100))}%`,
                }}
              />
            </div>
          )}
          {importError && <p className="mt-4 text-sm text-danger-muted">{importError}</p>}
        </Card>
      </main>
    </div>
  )
}
