import { useEffect, useState } from 'react'
import { Navigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { pagePaddingClass, pageShellClass } from '../utils/statusColors'
import Navigation from './Navigation'
import Card from './ui/Card'
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
  const { isAuthenticated, profile, updateProfile } = useAuth()
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
      <div className={pageShellClass}>
        <Navigation subtitle="Profile" />
        <main className={pagePaddingClass}>Loading profile...</main>
      </div>
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
    <div className={pageShellClass}>
      <Navigation subtitle="Profile" />

      <main className={`${pagePaddingClass} space-y-8`}>
        <Card className="p-8">
          <div className="flex flex-col items-center gap-4 sm:flex-row sm:items-start">
            <UserAvatar letter={form.avatar_letter} name={form.name} size="xl" />
            <div className="flex-1 text-center sm:text-left">
              <h2 className="text-2xl font-bold text-slate-900 dark:text-white">{form.name}</h2>
              <p className="mt-1 text-sm text-slate-500">
                Your avatar uses the first letter of your name. Photo upload coming soon.
              </p>
            </div>
          </div>
        </Card>

        <form onSubmit={handleSave} className="space-y-8">
          <Card className="p-6">
            <h3 className="text-lg font-semibold text-slate-900 dark:text-white">Basic info</h3>
            <div className="mt-4 grid gap-4 md:grid-cols-2">
              <label className="block">
                <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">Name</span>
                <input
                  value={form.name}
                  onChange={(e) => updateField('name', e.target.value)}
                  className="mt-2 w-full rounded-xl border border-slate-200 px-4 py-3 dark:border-white/10 dark:bg-gray-900"
                  required
                />
              </label>
              <label className="block">
                <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">Avatar letter</span>
                <input
                  value={form.avatar_letter || ''}
                  maxLength={1}
                  onChange={(e) => updateField('avatar_letter', e.target.value.toUpperCase())}
                  className="mt-2 w-full rounded-xl border border-slate-200 px-4 py-3 dark:border-white/10 dark:bg-gray-900"
                />
              </label>
              <label className="block">
                <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">Age</span>
                <input
                  type="number"
                  value={form.age}
                  onChange={(e) => updateField('age', e.target.value)}
                  className="mt-2 w-full rounded-xl border border-slate-200 px-4 py-3 dark:border-white/10 dark:bg-gray-900"
                />
              </label>
              <label className="block">
                <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">Weight (kg)</span>
                <input
                  type="number"
                  step="0.1"
                  value={form.weight}
                  onChange={(e) => updateField('weight', e.target.value)}
                  className="mt-2 w-full rounded-xl border border-slate-200 px-4 py-3 dark:border-white/10 dark:bg-gray-900"
                />
              </label>
            </div>
          </Card>

          <Card className="p-6">
            <h3 className="text-lg font-semibold text-slate-900 dark:text-white">Coaching preferences</h3>
            <p className="mt-1 text-sm text-slate-500">
              Saved permanently — your coach won't ask again unless you update these.
            </p>
            <div className="mt-4 grid gap-4 md:grid-cols-2">
              {FITNESS_FIELDS.map(({ key, label, type }) => (
                <label key={key} className={`block ${type === 'textarea' ? 'md:col-span-2' : ''}`}>
                  <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</span>
                  {type === 'textarea' ? (
                    <textarea
                      value={form[key] || ''}
                      onChange={(e) => updateField(key, e.target.value)}
                      rows={3}
                      className="mt-2 w-full rounded-xl border border-slate-200 px-4 py-3 dark:border-white/10 dark:bg-gray-900"
                    />
                  ) : (
                    <input
                      type={type}
                      value={form[key] ?? ''}
                      onChange={(e) => updateField(key, e.target.value)}
                      className="mt-2 w-full rounded-xl border border-slate-200 px-4 py-3 dark:border-white/10 dark:bg-gray-900"
                    />
                  )}
                </label>
              ))}
            </div>
          </Card>

          {message && <p className="text-sm text-sage">{message}</p>}
          {error && <p className="text-sm text-danger-muted">{error}</p>}

          <button
            type="submit"
            disabled={saving}
            className="rounded-xl bg-sage px-6 py-3 font-semibold text-white disabled:opacity-60"
          >
            {saving ? 'Saving...' : 'Save profile'}
          </button>
        </form>
      </main>
    </div>
  )
}
