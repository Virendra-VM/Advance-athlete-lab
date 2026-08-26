import { useState } from 'react'
import SplitsPanel from './SplitsPanel'
import { DetailTabs } from './detailShared'
import { ActivityDataGrid, TimelineStreams } from './StreamBlocks'

export default function SwimDetailBody({
  detail,
  metrics,
  chartData,
  streamPoints,
  fetchingStreams,
  streamMessage,
  dataRows,
  notesPanel = null,
}) {
  const tabs = [
    { id: 'laps', label: 'Laps' },
    { id: 'timeline', label: 'Timeline' },
    { id: 'data', label: 'Data' },
    { id: 'notes', label: 'Notes' },
  ]
  const [tab, setTab] = useState('laps')
  const laps = detail?.laps || []
  const summary = detail?.summary || {}

  return (
    <div className="space-y-4">
      <DetailTabs tabs={tabs} active={tab} onChange={setTab} />

      {tab === 'laps' && (
        <div className="space-y-3">
          {(summary.stroke_count != null ||
            summary.swolf != null ||
            summary.pool_length_m != null) && (
            <div className="grid gap-3 sm:grid-cols-3">
              {summary.pool_length_m != null ? (
                <div className="rounded-xl border border-[var(--aal-line)] px-3 py-2 text-sm">
                  <p className="text-[10px] uppercase tracking-wide text-[var(--aal-muted)]">Pool</p>
                  <p className="font-semibold tabular-nums">{summary.pool_length_m} m</p>
                </div>
              ) : null}
              {summary.stroke_count != null ? (
                <div className="rounded-xl border border-[var(--aal-line)] px-3 py-2 text-sm">
                  <p className="text-[10px] uppercase tracking-wide text-[var(--aal-muted)]">
                    Strokes
                  </p>
                  <p className="font-semibold tabular-nums">{summary.stroke_count}</p>
                </div>
              ) : null}
              {summary.swolf != null ? (
                <div className="rounded-xl border border-[var(--aal-line)] px-3 py-2 text-sm">
                  <p className="text-[10px] uppercase tracking-wide text-[var(--aal-muted)]">SWOLF</p>
                  <p className="font-semibold tabular-nums">{Math.round(summary.swolf)}</p>
                </div>
              ) : null}
            </div>
          )}
          <SplitsPanel family="swim" laps={laps} points={streamPoints || chartData} />
        </div>
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
