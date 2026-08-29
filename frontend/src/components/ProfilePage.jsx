import { useEffect, useState } from 'react'
import { Navigate } from 'react-router-dom'
import { LogOut } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import AppShell from './layout/AppShell'
import PageHeader from './ui/PageHeader'
import SectionCard from './ui/SectionCard'
import UserAvatar from './UserAvatar'

const FITNESS_FIELDS = [
  { key: 'primary_goal', label: 'Primary goal', type: 'textarea' },
  { key: 'secondary_goal', label: 'Secondary goal', type: 'textarea' },
  { key: 'equipment', label: 'Equipment access', type: 'textarea' },
  { key: 'days_per_week', label: 'Days per week', type: 'number' },
  { key: 'workout_duration_minutes', label: 'Workout duration (min)', type: 'number' },
  { key: 'preferred_workout_time', label: 'Preferred workout time', type: 'text' },
  { key: 'injuries_limitations', label: 'Injuries / limitations', type: 'textarea' },
  { key: 'fitness_level', label: 'Fitness level', type: 'text' },
  { key: 'exercises_hate', label: 'Exercises you dislike', type: 'textarea' },
  { key: 'exercises_love', label: 'Exercises you love', type: 'textarea' },
]

export default function ProfilePage() {
  const { isAuthenticated, profile, updateProfile, logout } = useAuth()
  const [form, setForm] = useState(null)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    if (profile) {
      setForm({ ...profile })
    }
  }, [profile])

  if (!isAuthenticated) return <Navigate to="/signin" replace />
  if (!form) {
    return (
      <AppShell title="Profile">
        <p className="text-sm text-[var(--aal-muted)]">Loading profile...</p>
      </AppShell>
    )
  }

  function updateField(key, value) {
    setForm((prev) => ({ ...prev, [key]: value }))
  }

  async function handleSave(event) {
    event.preventDefault()
    setSaving(true)
    setError('')
    setMessage('')
    try {
      const payload = {
        name: form.name,
        age: Number(form.age),
        weight: Number(form.weight),
        avatar_letter: form.avatar_letter?.slice(0, 1).toUpperCase(),
        primary_goal: form.primary_goal,
        secondary_goal: form.secondary_goal,
        equipment: form.equipment,
        days_per_week: form.days_per_week ? Number(form.days_per_week) : null,
        workout_duration_minutes: form.workout_duration_minutes
          ? Number(form.workout_duration_minutes)
          : null,
        preferred_workout_time: form.preferred_workout_time,
        injuries_limitations: form.injuries_limitations,
        fitness_level: form.fitness_level,
        exercises_hate: form.exercises_hate,
        exercises_love: form.exercises_love,
      }
      await updateProfile(payload)
      setMessage('Profile saved. Your coach will remember these answers.')
    } catch (err) {
      setError(err.message || 'Failed to save profile.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <AppShell title="Profile">
      <div className="w-full space-y-8">
        <PageHeader
          eyebrow="Account"
          title="Profile"
          subtitle="Basics and coaching preferences used for future AI plans."
          actions={
            <button
              type="button"
              onClick={logout}
              className="inline-flex items-center gap-2 rounded-xl border border-danger-muted/40 px-4 py-2.5 text-sm font-semibold text-danger-muted transition hover:bg-danger-muted/5"
            >
              <LogOut className="h-4 w-4" />
              Log out
            </button>
          }
        />

        <SectionCard>
          <div className="flex flex-col items-center gap-4 sm:flex-row sm:items-start">
            <UserAvatar letter={form.avatar_letter} name={form.name} size="xl" />
            <div className="flex-1 text-center sm:text-left">
              <h2 className="text-2xl font-bold">{form.name}</h2>
              <p className="mt-1 text-sm text-[var(--aal-muted)]">
                Your avatar uses the first letter of your name. Photo upload coming soon.
              </p>
            </div>
          </div>
        </SectionCard>

        <form onSubmit={handleSave} className="space-y-8">
          <SectionCard title="Basic info">
            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
              <label className="block">
                <span className="text-xs font-semibold uppercase tracking-wide text-[var(--aal-muted)]">
                  Name
                </span>
                <input
                  value={form.name}
                  onChange={(e) => updateField('name', e.target.value)}
                  className="mt-2 w-full rounded-xl border border-[var(--aal-line)] bg-[var(--aal-card)] px-4 py-3"
                  required
                />
              </label>
              <label className="block">
                <span className="text-xs font-semibold uppercase tracking-wide text-[var(--aal-muted)]">
                  Avatar letter
                </span>
                <input
                  value={form.avatar_letter || ''}
                  maxLength={1}
                  onChange={(e) => updateField('avatar_letter', e.target.value.toUpperCase())}
                  className="mt-2 w-full rounded-xl border border-[var(--aal-line)] bg-[var(--aal-card)] px-4 py-3"
                />
              </label>
              <label className="block">
                <span className="text-xs font-semibold uppercase tracking-wide text-[var(--aal-muted)]">
                  Age
                </span>
                <input
                  type="number"
                  value={form.age}
                  onChange={(e) => updateField('age', e.target.value)}
                  className="mt-2 w-full rounded-xl border border-[var(--aal-line)] bg-[var(--aal-card)] px-4 py-3"
                />
              </label>
              <label className="block">
                <span className="text-xs font-semibold uppercase tracking-wide text-[var(--aal-muted)]">
                  Weight (kg)
                </span>
                <input
                  type="number"
                  step="0.1"
                  value={form.weight}
                  onChange={(e) => updateField('weight', e.target.value)}
                  className="mt-2 w-full rounded-xl border border-[var(--aal-line)] bg-[var(--aal-card)] px-4 py-3"
                />
              </label>
            </div>
          </SectionCard>

          <SectionCard
            title="Coaching preferences"
            subtitle="Saved permanently — your coach won't ask again unless you update these."
          >
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
              {FITNESS_FIELDS.map(({ key, label, type }) => (
                <label
                  key={key}
                  className={`block ${type === 'textarea' ? 'md:col-span-2 xl:col-span-3' : ''}`}
                >
                  <span className="text-xs font-semibold uppercase tracking-wide text-[var(--aal-muted)]">
                    {label}
                  </span>
                  {type === 'textarea' ? (
                    <textarea
                      value={form[key] || ''}
                      onChange={(e) => updateField(key, e.target.value)}
                      rows={3}
                      className="mt-2 w-full rounded-xl border border-[var(--aal-line)] bg-[var(--aal-card)] px-4 py-3"
                    />
                  ) : (
                    <input
                      type={type}
                      value={form[key] ?? ''}
                      onChange={(e) => updateField(key, e.target.value)}
                      className="mt-2 w-full rounded-xl border border-[var(--aal-line)] bg-[var(--aal-card)] px-4 py-3"
                    />
                  )}
                </label>
              ))}
            </div>
          </SectionCard>

          {message && <p className="text-sm text-sage">{message}</p>}
          {error && <p className="text-sm text-danger-muted">{error}</p>}

          <div className="flex flex-wrap items-center gap-3">
            <button
              type="submit"
              disabled={saving}
              className="rounded-xl bg-sage px-6 py-3 font-semibold text-white disabled:opacity-60"
            >
              {saving ? 'Saving...' : 'Save profile'}
            </button>
            <button
              type="button"
              onClick={logout}
              className="inline-flex items-center gap-2 rounded-xl border border-danger-muted/40 px-5 py-3 text-sm font-semibold text-danger-muted transition hover:bg-danger-muted/5"
            >
              <LogOut className="h-4 w-4" />
              Log out
            </button>
          </div>
        </form>
      </div>
    </AppShell>
  )
}
