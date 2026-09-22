import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Activity, RefreshCw } from 'lucide-react'
import OnboardingField from '../onboarding/OnboardingFields'
import {
  applyPhysiologyEstimate,
  applyTestSuggestion,
  getTrainingZones,
  previewPhysiologyEstimate,
} from '../../api/auth'
import { DisplayValue, FactorItem } from './ProfileParts'

export const ZONE_ANCHOR_FIELDS = [
  {
    key: 'ftp_watts',
    label: 'Cycling FTP (watts)',
    type: 'number',
    min: 50,
    max: 500,
  },
  {
    key: 'lthr_bpm',
    label: 'Lactate threshold HR (bpm)',
    type: 'number',
    min: 90,
    max: 230,
  },
  {
    key: 'bike_lthr_bpm',
    label: 'Cycling LTHR (bpm)',
    type: 'number',
    min: 90,
    max: 230,
  },
  {
    key: 'max_hr_bpm',
    label: 'Max heart rate (bpm)',
    type: 'number',
    min: 120,
    max: 230,
  },
  {
    key: 'resting_hr_bpm',
    label: 'Resting heart rate (bpm)',
    type: 'number',
    min: 30,
    max: 120,
  },
  {
    key: 'threshold_pace',
    label: 'Threshold run pace',
    type: 'text',
    placeholder: '4:30/km',
  },
  {
    key: 'lt1_pace',
    label: 'LT1 / aerobic threshold pace',
    type: 'text',
    placeholder: '5:00/km',
  },
  {
    key: 'marathon_pace',
    label: 'Marathon pace',
    type: 'text',
    placeholder: '4:45/km',
  },
  {
    key: 'css_pace',
    label: 'Swim CSS pace',
    type: 'text',
    placeholder: '1:35/100m',
  },
  {
    key: 'vo2max',
    label: 'VO₂ max',
    type: 'number',
    min: 20,
    max: 90,
  },
  {
    key: 'zone_run_hr_method',
    label: 'Run HR zone model',
    type: 'chips-single',
    options: [
      { value: 'lthr', label: 'LTHR (Friel)' },
      { value: 'max_hr', label: 'Max HR %' },
      { value: 'hrr', label: 'Heart-rate reserve' },
    ],
  },
]

function zoneMethodLabel(method) {
  if (method === 'hrr') return 'Heart-rate reserve'
  if (method === 'max_hr') return 'Max HR %'
  return 'LTHR (Friel)'
}

function ZoneTable({ title, rows }) {
  if (!rows?.length) return null
  return (
    <div>
      <p className="mb-2 text-xs font-semibold uppercase tracking-[0.12em] text-[var(--aal-muted)]">
        {title}
      </p>
      <div className="grid gap-1 text-sm">
        {rows.map((row) => (
          <div key={row.name} className="flex justify-between gap-4">
            <span className="text-[var(--aal-muted)]">{row.name}</span>
            <span className="font-medium text-[var(--aal-ink)]">{row.range || '—'}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

function ZonesTables({ zones }) {
  if (!zones) {
    return <p className="text-sm text-[var(--aal-muted)]">Loading training zones…</p>
  }

  const hasZones =
    (zones.power_zones?.length || 0) +
      (zones.hr_zones?.length || 0) +
      (zones.run_pace_zones?.length || 0) +
      (zones.swim_pace_zones?.length || 0) >
    0

  if (!hasZones) {
    return (
      <p className="text-sm text-[var(--aal-muted)]">
        Add anchors above or estimate from recent activities to generate zone tables.
      </p>
    )
  }

  return (
    <div className="space-y-5 rounded-2xl border border-[var(--aal-line)] bg-[var(--aal-card)]/60 p-4">
      <p className="text-xs text-[var(--aal-muted)]">
        Run HR: {zoneMethodLabel(zones.methods?.run_hr)} · Bike power: Coggan % FTP
      </p>
      <ZoneTable
        title="Run heart rate"
        rows={(zones.hr_zones || []).map((z) => ({
          name: z.name,
          range: z.low_bpm != null ? `${z.low_bpm}–${z.high_bpm} bpm` : null,
        }))}
      />
      <ZoneTable
        title="Run pace"
        rows={(zones.run_pace_zones || []).map((z) => ({
          name: z.name,
          range: z.low_pace && z.high_pace ? `${z.low_pace} – ${z.high_pace}` : null,
        }))}
      />
      <ZoneTable
        title="Bike power"
        rows={(zones.power_zones || []).map((z) => ({
          name: z.name,
          range: z.low_w != null ? `${z.low_w}–${z.high_w} W` : null,
        }))}
      />
      <ZoneTable
        title="Swim pace"
        rows={(zones.swim_pace_zones || []).map((z) => ({
          name: z.name,
          range: z.low_pace && z.high_pace ? `${z.low_pace} – ${z.high_pace}` : null,
        }))}
      />
    </div>
  )
}

function NudgesList({ nudges }) {
  if (!nudges?.length) return null
  return (
    <div className="space-y-2">
      {nudges.map((nudge) => (
        <p
          key={nudge.code}
          className="rounded-xl border border-amber-200/60 bg-amber-50/80 px-4 py-3 text-sm text-[var(--aal-ink)] dark:border-amber-900/40 dark:bg-amber-950/30"
        >
          {nudge.message}
        </p>
      ))}
    </div>
  )
}

export function TrainingZonesView({ form }) {
  const [zones, setZones] = useState(null)
  const [nudges, setNudges] = useState([])

  const loadZones = useCallback(() => {
    getTrainingZones()
      .then(setZones)
      .catch(() => setZones(null))
    previewPhysiologyEstimate()
      .then((result) => setNudges(result.nudges || []))
      .catch(() => setNudges([]))
  }, [])

  useEffect(() => {
    loadZones()
  }, [loadZones, form?.threshold_pace, form?.ftp_watts, form?.lthr_bpm])

  return (
    <div className="space-y-6">
      <NudgesList nudges={nudges} />
      <div className="grid gap-4 sm:grid-cols-2">
        <FactorItem label="FTP">
          <DisplayValue>
            {form.ftp_watts != null
              ? `${form.ftp_watts} W`
              : form.ftp_estimated_watts != null
                ? `Estimated ${form.ftp_estimated_watts} W`
                : null}
          </DisplayValue>
        </FactorItem>
        <FactorItem label="LT2 / LTHR">
          <DisplayValue>{form.lthr_bpm != null ? `${form.lthr_bpm} bpm` : null}</DisplayValue>
        </FactorItem>
        <FactorItem label="Max HR">
          <DisplayValue>{form.max_hr_bpm != null ? `${form.max_hr_bpm} bpm` : null}</DisplayValue>
        </FactorItem>
        <FactorItem label="Threshold pace">
          <DisplayValue>{form.threshold_pace_display || form.threshold_pace}</DisplayValue>
        </FactorItem>
        <FactorItem label="Swim CSS">
          <DisplayValue>{form.css_pace_display || form.css_pace}</DisplayValue>
        </FactorItem>
        <FactorItem label="Run HR model">
          <DisplayValue>{zoneMethodLabel(form.zone_run_hr_method)}</DisplayValue>
        </FactorItem>
      </div>
      <ZonesTables zones={zones} />
      <p className="text-xs text-[var(--aal-muted)]">
        For lab-grade updates, add a{' '}
        <Link to="/season" className="font-medium text-sage underline-offset-2 hover:underline">
          D-race test event
        </Link>{' '}
        on your season plan (FTP or LTHR protocol).
      </p>
    </div>
  )
}

export function TrainingZonesEditor({
  form,
  onChange,
  onEstimateApplied,
}) {
  const [zones, setZones] = useState(null)
  const [preview, setPreview] = useState(null)
  const [nudges, setNudges] = useState([])
  const [estimating, setEstimating] = useState(false)
  const [estimateMessage, setEstimateMessage] = useState('')

  const loadZones = useCallback(() => {
    getTrainingZones()
      .then(setZones)
      .catch(() => setZones(null))
  }, [])

  useEffect(() => {
    loadZones()
  }, [loadZones])

  async function handlePreviewEstimate() {
    setEstimating(true)
    setEstimateMessage('')
    try {
      const result = await previewPhysiologyEstimate()
      setPreview(result)
      setNudges(result.nudges || [])
      const count = Object.keys(result.suggestions || {}).length
      setEstimateMessage(
        count
          ? `Found ${count} value${count > 1 ? 's' : ''} from ${result.activity_count || 0} recent activities.`
          : 'No new estimates — your anchors are already set or we need more synced activities.',
      )
    } catch (err) {
      setEstimateMessage(err.message || 'Could not estimate from activities.')
    } finally {
      setEstimating(false)
    }
  }

  async function handleApplyEstimate() {
    setEstimating(true)
    setEstimateMessage('')
    try {
      const result = await applyPhysiologyEstimate()
      setPreview(null)
      setZones(result.zones)
      setNudges(result.nudges || [])
      const applied = Object.keys(result.applied || {})
      setEstimateMessage(
        applied.length
          ? `Applied ${applied.join(', ')} from recent activities.`
          : 'Nothing to apply — profile anchors already filled.',
      )
      onEstimateApplied?.(result)
    } catch (err) {
      setEstimateMessage(err.message || 'Could not apply estimates.')
    } finally {
      setEstimating(false)
    }
  }

  async function handleApplySuggestion(suggestionId) {
    setEstimating(true)
    setEstimateMessage('')
    try {
      const result = await applyTestSuggestion(suggestionId)
      setZones(result.zones)
      setPreview((current) =>
        current
          ? {
              ...current,
              test_suggestions: (current.test_suggestions || []).filter(
                (row) => row.id !== suggestionId,
              ),
            }
          : current,
      )
      setEstimateMessage(`Applied ${Object.keys(result.applied || {}).join(', ')} from test activity.`)
      onEstimateApplied?.(result)
    } catch (err) {
      setEstimateMessage(err.message || 'Could not apply test suggestion.')
    } finally {
      setEstimating(false)
    }
  }

  return (
    <div className="space-y-8">
      <NudgesList nudges={nudges} />
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold uppercase tracking-[0.14em] text-[var(--aal-muted)]">
            Anchor values
          </h3>
          <p className="mt-1 text-sm text-[var(--aal-muted)]">
            Zones update live as you edit. Leave blank to estimate from synced activities.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={handlePreviewEstimate}
            disabled={estimating}
            className="inline-flex items-center gap-2 rounded-xl border border-[var(--aal-line)] px-3 py-2 text-sm font-medium text-[var(--aal-ink)] disabled:opacity-50"
          >
            <Activity className="h-4 w-4" />
            Preview estimate
          </button>
          <button
            type="button"
            onClick={handleApplyEstimate}
            disabled={estimating}
            className="inline-flex items-center gap-2 rounded-xl bg-sage px-3 py-2 text-sm font-semibold text-white disabled:opacity-50"
          >
            <RefreshCw className={`h-4 w-4 ${estimating ? 'animate-spin' : ''}`} />
            Apply from activities
          </button>
        </div>
      </div>

      {estimateMessage ? (
        <p className="rounded-xl bg-sage/10 px-4 py-3 text-sm text-[var(--aal-ink)]">{estimateMessage}</p>
      ) : null}

      {preview?.test_suggestions?.length ? (
        <div className="rounded-xl border border-[var(--aal-line)] px-4 py-3 text-sm">
          <p className="mb-3 font-medium text-[var(--aal-ink)]">Detected test activities</p>
          <ul className="space-y-3">
            {preview.test_suggestions.map((hit) => (
              <li
                key={hit.id}
                className="flex flex-col gap-2 rounded-lg bg-[var(--aal-card)]/70 p-3 sm:flex-row sm:items-center sm:justify-between"
              >
                <div>
                  <p className="font-medium text-[var(--aal-ink)]">{hit.activity_name}</p>
                  <p className="text-[var(--aal-muted)]">
                    {hit.field} → {hit.value} ({hit.confidence}) — {hit.reason}
                  </p>
                </div>
                <button
                  type="button"
                  disabled={estimating}
                  onClick={() => handleApplySuggestion(hit.id)}
                  className="rounded-lg bg-sage px-3 py-2 text-xs font-semibold text-white disabled:opacity-50"
                >
                  Apply
                </button>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {preview?.suggestions && Object.keys(preview.suggestions).length > 0 ? (
        <div className="rounded-xl border border-[var(--aal-line)] px-4 py-3 text-sm">
          <p className="mb-2 font-medium text-[var(--aal-ink)]">Suggested values</p>
          <ul className="space-y-1 text-[var(--aal-muted)]">
            {Object.entries(preview.suggestions).map(([key, value]) => (
              <li key={key}>
                {key}: <span className="font-medium text-[var(--aal-ink)]">{String(value)}</span>
                {preview.sources?.[key] ? ` (${preview.sources[key]})` : ''}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      <div className="grid gap-6 md:grid-cols-2">
        {ZONE_ANCHOR_FIELDS.map((field) => (
          <OnboardingField
            key={field.key}
            field={field}
            answers={form}
            value={form[field.key]}
            onChange={(value) => onChange(field.key, value)}
          />
        ))}
      </div>

      <div>
        <h3 className="mb-4 text-sm font-semibold uppercase tracking-[0.14em] text-[var(--aal-muted)]">
          Live zone tables
        </h3>
        <ZonesTables zones={zones} />
      </div>

      <p className="text-xs text-[var(--aal-muted)]">
        After a formal test, add a{' '}
        <Link to="/season" className="font-medium text-sage underline-offset-2 hover:underline">
          D-race checkpoint
        </Link>{' '}
        to record FTP or LTHR and lock in zones from the result.
      </p>
    </div>
  )
}
