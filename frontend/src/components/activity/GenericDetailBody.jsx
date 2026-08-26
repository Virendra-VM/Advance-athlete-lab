import { useState } from 'react'
import { DetailTabs } from './detailShared'
import { ActivityDataGrid, TimelineStreams } from './StreamBlocks'

export default function GenericDetailBody({
  detail,
  metrics,
  chartData,
  fetchingStreams,
  streamMessage,
  dataRows,
  familyLabel,
  notesPanel = null,
}) {
  const tabs = [
    { id: 'overview', label: 'Overview' },
    { id: 'timeline', label: 'Timeline' },
    { id: 'data', label: 'Data' },
    { id: 'notes', label: 'Notes' },
  ]
  const [tab, setTab] = useState('overview')
  const summary = detail?.summary || {}
  const sources = detail?.sources || []

  return (
    <div className="space-y-4">
      <DetailTabs tabs={tabs} active={tab} onChange={setTab} />

      {tab === 'overview' && (
        <section className="rounded-2xl border border-[var(--aal-line)] bg-[var(--aal-card)] p-5">
          <h2 className="text-lg font-semibold">{familyLabel || 'Session'} overview</h2>
          <p className="mt-1 text-sm text-[var(--aal-muted)]">
            Key metrics are in the header. Timeline streams appear when FIT or Strava data is available.
          </p>
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            {summary.description ? (
              <div className="sm:col-span-2">
                <p className="text-[10px] uppercase tracking-wide text-[var(--aal-muted)]">Notes from source</p>
                <p className="mt-1 text-sm whitespace-pre-wrap">{summary.description}</p>
              </div>
            ) : null}
            <div>
              <p className="text-[10px] uppercase tracking-wide text-[var(--aal-muted)]">Detail sources</p>
              <p className="mt-1 text-sm">
                {sources.length ? sources.map((s) => s.toUpperCase()).join(' + ') : 'Summary only'}
              </p>
            </div>
            {summary.calories != null ? (
              <div>
                <p className="text-[10px] uppercase tracking-wide text-[var(--aal-muted)]">Calories</p>
                <p className="mt-1 text-sm font-semibold tabular-nums">{Math.round(summary.calories)}</p>
              </div>
            ) : null}
          </div>
        </section>
      )}

      {tab === 'timeline' && (
        <TimelineStreams
          metrics={metrics}
          chartData={chartData}
          fetchingStreams={fetchingStreams}
          streamMessage={streamMessage}
          prefer="hr"
        />
      )}

      {tab === 'data' && <ActivityDataGrid rows={dataRows} />}
      {tab === 'notes' && notesPanel}
    </div>
  )
}
