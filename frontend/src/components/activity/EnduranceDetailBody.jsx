import { useState } from 'react'
import SplitsPanel from './SplitsPanel'
import { DetailTabs } from './detailShared'
import { ActivityDataGrid, StreamPanel, TimelineStreams } from './StreamBlocks'

export default function EnduranceDetailBody({
  family,
  detail,
  metrics,
  chartData,
  streamPoints,
  fetchingStreams,
  streamMessage,
  dataRows,
  notesPanel = null,
}) {
  const isRide = family === 'ride'
  const tabs = [
    { id: 'splits', label: 'Splits' },
    { id: 'timeline', label: 'Timeline' },
    { id: isRide ? 'power' : 'hr', label: isRide ? 'Power' : 'HR' },
    { id: 'data', label: 'Data' },
    { id: 'notes', label: 'Notes' },
  ]
  const [tab, setTab] = useState('splits')
  const laps = detail?.laps || []

  return (
    <div className="space-y-4">
      <DetailTabs tabs={tabs} active={tab} onChange={setTab} />

      {tab === 'splits' && (
        <SplitsPanel family={family} laps={laps} points={streamPoints || chartData} />
      )}

      {tab === 'timeline' && (
        <TimelineStreams
          metrics={metrics}
          chartData={chartData}
          fetchingStreams={fetchingStreams}
          streamMessage={streamMessage}
          prefer={isRide ? 'power' : 'hr'}
        />
      )}

      {tab === 'hr' && (
        <div className="space-y-3">
          {metrics.includes('heart_rate') ? (
            <StreamPanel
              title="Heart rate"
              unit="bpm"
              dataKey="heart_rate"
              color="#ef4444"
              data={chartData}
            />
          ) : (
            <p className="text-sm text-[var(--aal-muted)]">No heart-rate stream for this activity.</p>
          )}
        </div>
      )}

      {tab === 'power' && (
        <div className="space-y-3">
          {metrics.includes('power') ? (
            <StreamPanel
              title="Power"
              unit="W"
              dataKey="power"
              color="#8b5cf6"
              data={chartData}
              area
            />
          ) : (
            <p className="text-sm text-[var(--aal-muted)]">No power stream for this activity.</p>
          )}
        </div>
      )}

      {tab === 'data' && <ActivityDataGrid rows={dataRows} />}
      {tab === 'notes' && notesPanel}
    </div>
  )
}
