import { useAuth } from '../context/AuthContext'
import ActivitiesTable from '../components/ActivitiesTable'
import AppShell from '../components/layout/AppShell'
import PageHeader from '../components/ui/PageHeader'

export default function ActivitiesPage() {
  const { profile } = useAuth()
  return (
    <AppShell title="Activities">
      <PageHeader
        eyebrow="Activities"
        title="All activities"
        subtitle="Search, filter, and page through Strava and COROS sessions."
      />
      <ActivitiesTable athleteProfileId={profile?.id} />
    </AppShell>
  )
}
