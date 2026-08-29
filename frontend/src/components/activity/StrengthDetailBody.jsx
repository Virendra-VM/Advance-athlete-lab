import { useState } from 'react'
import ExerciseList from './ExerciseList'
import { DetailTabs } from './detailShared'
import { ActivityDataGrid, StreamPanel, TimelineStreams } from './StreamBlocks'

export default function StrengthDetailBody({
  detail,
  metrics,
  chartData,
  fetchingStreams,
  streamMessage,
  dataRows,
  notesPanel = null,
}) {
  const tabs = [
    { id: 'workout', label: 'Workout' },
    { id: 'hr', label: 'HR' },
    { id: 'data', label: 'Data' },
    { id: 'notes', label: 'Notes' },
  ]
  const [tab, setTab] = useState('workout')
  const exercises = detail?.exercises || []

  return (
    <div className="space-y-4">
      <DetailTabs tabs={tabs} active={tab} onChange={setTab} />

      {tab === 'workout' && <ExerciseList exercises={exercises} />}

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
            <TimelineStreams
              metrics={metrics}
              chartData={chartData}
              fetchingStreams={fetchingStreams}
              streamMessage={streamMessage || 'No heart-rate stream for this strength session.'}
              prefer="hr"
            />
          )}
        </div>
      )}

      {tab === 'data' && <ActivityDataGrid rows={dataRows} />}
      {tab === 'notes' && notesPanel}
    </div>
  )
}
