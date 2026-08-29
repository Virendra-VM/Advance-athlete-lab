import { useEffect, useState } from 'react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { getAthleteStats } from '../api/athlete'
import { useAuth } from '../context/AuthContext'
import BarActiveGlow from '../components/charts/BarActiveEffects'
import AppShell from '../components/layout/AppShell'
import ACWRGauge from '../components/ACWRGauge'
import AcuteChronicCards from '../components/AcuteChronicCards'
import LoadingDots from '../components/ui/LoadingDots'
import PageHeader from '../components/ui/PageHeader'
import SectionCard from '../components/ui/SectionCard'

export default function VolumePage() {
  const { profile } = useAuth()
  const [stats, setStats] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!profile?.id) return
    setLoading(true)
    getAthleteStats(profile.id)
      .then(setStats)
      .catch((err) => setError(err.message || 'Failed to load volume stats.'))
      .finally(() => setLoading(false))
  }, [profile?.id])

  const volumeData = (stats?.weekly_volume_history || []).map((bucket) => ({
    label: bucket.week_label,
    km: bucket.total_distance_km,
  }))

  return (
    <AppShell title="Volume & ACWR">
      <PageHeader
        eyebrow="Training"
        title="Volume & ACWR"
        subtitle="Distance-based acute/chronic workload from synced activities."
      />
      {error && <p className="mb-4 text-sm text-danger-muted">{error}</p>}
      {loading && <LoadingDots label="Loading volume…" />}
      {!loading && stats && (
        <div className="space-y-6">
          <AcuteChronicCards
            acuteLoadKm={Number(stats.acute_load_km || 0)}
            chronicLoadKm={Number(stats.chronic_load_km || 0)}
          />
          <div className="grid gap-6 xl:grid-cols-3">
            <SectionCard title="ACWR">
              <ACWRGauge acwr={stats.acwr ?? 0} />
            </SectionCard>
            <SectionCard title="8-week volume" className="xl:col-span-2">
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={volumeData}>
                    <CartesianGrid stroke="var(--aal-line)" strokeDasharray="3 3" />
                    <XAxis dataKey="label" tick={{ fontSize: 12 }} />
                    <YAxis tick={{ fontSize: 12 }} />
                    <Tooltip cursor={{ fill: 'transparent' }} />
                    <Bar
                      dataKey="km"
                      fill="#6b9080"
                      radius={[6, 6, 0, 0]}
                      activeBar={BarActiveGlow}
                    />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </SectionCard>
          </div>
        </div>
      )}
    </AppShell>
  )
}
