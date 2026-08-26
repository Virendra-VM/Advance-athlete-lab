import { useState } from 'react'
import { useAuth } from '../context/AuthContext'
import ActivitiesTable from '../components/ActivitiesTable'
import AppShell from '../components/layout/AppShell'
import PageHeader from '../components/ui/PageHeader'
import RangeTabs from '../components/ui/RangeTabs'
import { ACTIVITY_RANGE_OPTIONS } from '../utils/activityRanges'

export default function ActivitiesPage() {
  const { profile } = useAuth()
  const [range, setRange] = useState('month')

  return (
    <AppShell title="Activities" flush>
      <div className="flex min-h-0 flex-1 flex-col overflow-hidden px-4 py-6 pt-14 sm:px-6 lg:px-8 lg:pt-6">
        <div className="shrink-0">
          <PageHeader
            className="!mb-4"
            eyebrow="Activities"
            title="All activities"
            subtitle="Search, filter, and page through Strava and COROS sessions."
            actions={
              <RangeTabs
                value={range}
                onChange={setRange}
                options={ACTIVITY_RANGE_OPTIONS}
              />
            }
          />
        </div>
        <ActivitiesTable
          key={range}
          athleteProfileId={profile?.id}
          range={range}
          onRangeChange={setRange}
          fill
        />
      </div>
    </AppShell>
  )
}
