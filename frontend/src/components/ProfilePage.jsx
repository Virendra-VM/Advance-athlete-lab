import { useEffect, useMemo, useState } from 'react'
import { Navigate, useBlocker, useLocation } from 'react-router-dom'
import { motion } from 'framer-motion'
import { Pencil } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import AppShell from './layout/AppShell'
import PageHeader from './ui/PageHeader'
import SectionCard from './ui/SectionCard'
import UserAvatar from './UserAvatar'
import OnboardingField from './onboarding/OnboardingFields'
import ProfileEventsPanel from './season/ProfileEventsPanel'
import CycleTrackingFields, { CycleTrackingView } from './profile/CycleTrackingPanel'
import { getCycleContext } from '../api/cycle'
import {
  BodyView,
  FactStrip,
  HealthView,
  IdentityEditFields,
  IdentityFocus,
  JumpNav,
  LeaveGuard,
  MeasureFields,
  MissingCompleteness,
  PreferencesView,
  SectionEditButton,
  SettingsHint,
  SportPills,
  StickySaveBar,
  TrainingView,
} from './profile/ProfileParts'
import {
  displayAge,
  formsEqual,
  missingCompletenessItems,
  scrollToProfileSection,
  sectionFromHash,
  toDateInput,
  toNumberOrNull,
  toTextOrNull,
} from '../utils/profileView'

const fadeUp = {
  hidden: { opacity: 0, y: 12 },
  show: { opacity: 1, y: 0, transition: { duration: 0.35, ease: 'easeOut' } },
}

const GOAL_FIELDS = [
  { key: 'primary_goal', label: 'Primary goal', type: 'textarea' },
  { key: 'secondary_goal', label: 'Secondary goal', type: 'textarea' },
  { key: 'goal_event_name', label: 'Goal event', type: 'text' },
  { key: 'goal_event_date', label: 'Event date', type: 'date' },
  { key: 'goal_metric', label: 'Target result', type: 'text' },
]

const FITNESS_FIELDS = [
  {
    key: 'fitness_level',
    label: 'Fitness level',
    type: 'chips-single',
    options: ['Complete beginner', 'Beginner', 'Intermediate', 'Advanced'],
  },
  {
    key: 'training_history_months',
    label: 'How long have you been training consistently?',
    type: 'chips-single',
    options: [
      { value: 0, label: 'Just starting' },
      { value: 3, label: '~3 months' },
      { value: 6, label: '~6 months' },
      { value: 12, label: '1 year' },
      { value: 36, label: '3+ years' },
      { value: 60, label: '5+ years' },
    ],
  },
  { key: 'current_weekly_volume', type: 'weekly-volume' },
  { key: 'longest_recent_session', label: 'Longest recent session', type: 'text' },
  { key: 'race_prs', label: 'Recent results / PRs', type: 'textarea' },
]

const PHYSIOLOGY_FIELDS = [
  {
    key: 'ftp_watts',
    label: 'Cycling FTP (watts)',
    type: 'number',
    min: 50,
    max: 500,
    help: 'Functional threshold power. Leave blank to use an estimate from recent rides.',
  },
  {
    key: 'lthr_bpm',
    label: 'Lactate threshold HR (bpm)',
    type: 'number',
    min: 90,
    max: 230,
    help: 'LT2 / LTHR if you have it from a test or device.',
  },
  {
    key: 'max_hr_bpm',
    label: 'Max heart rate (bpm)',
    type: 'number',
    min: 120,
    max: 230,
    help: 'Leave blank to use the highest recent peak, or 220 minus age as a last resort.',
  },
]

const TIME_FIELDS = [
  {
    key: 'days_per_week',
    label: 'Training days per week',
    type: 'chips-single',
    options: [1, 2, 3, 4, 5, 6, 7],
  },
  {
    key: 'workout_duration_minutes',
    label: 'Typical session length',
    help: 'Usual weekday length. Long rides and key sessions can be much longer.',
    type: 'chips-single',
    options: [
      { value: 20, label: '20 min' },
      { value: 30, label: '30 min' },
      { value: 45, label: '45 min' },
      { value: 60, label: '60 min' },
      { value: 90, label: '90 min' },
      { value: 120, label: '2 hr' },
    ],
  },
  {
    key: 'weekly_minutes_budget',
    label: 'Weekly minutes budget',
    type: 'number',
    min: 0,
    max: 3000,
    help: 'A soft weekly target, not days × typical session. Leave blank if unsure.',
  },
  {
    key: 'preferred_workout_time',
    label: 'Preferred time of day',
    type: 'chips-single',
    options: ['Morning', 'Lunch', 'Evening', 'Flexible'],
  },
]

const BODY_FIELDS = [
  {
    key: 'sex',
    label: 'Sex',
    type: 'chips-single',
    options: [
      { value: 'female', label: 'Female' },
      { value: 'male', label: 'Male' },
      { value: 'other', label: 'Other' },
      { value: 'prefer_not', label: 'Prefer not to say' },
    ],
  },
  { key: 'date_of_birth', label: 'Date of birth', type: 'date' },
  {
    key: 'units',
    label: 'Preferred units',
    type: 'chips-single',
    options: [
      { value: 'metric', label: 'Metric (km, kg)' },
      { value: 'imperial', label: 'Imperial (mi, lb)' },
    ],
  },
]

const PREFERENCE_FIELDS = [
  {
    key: 'equipment',
    label: 'Equipment access',
    type: 'chips-multi',
    options: [
      'Full gym',
      'Home dumbbells',
      'Barbell + rack',
      'Bodyweight only',
      'Resistance bands',
      'Kettlebells',
      'Pull-up bar',
      'Cardio machines',
      'Road bike',
      'Indoor trainer',
      'Pool access',
    ],
  },
  { key: 'exercises_love', label: 'Sessions you love', type: 'textarea' },
  { key: 'exercises_hate', label: 'Sessions you hate', type: 'textarea' },
]

function buildForm(profile) {
  if (!profile) return null
  return {
    ...profile,
    date_of_birth: toDateInput(profile.date_of_birth),
    goal_event_date: toDateInput(profile.goal_event_date),
    sports: profile.sports || [],
    injuries: profile.injuries || [],
    current_weekly_volume:
      profile.current_weekly_volume && !Array.isArray(profile.current_weekly_volume)
        ? profile.current_weekly_volume
        : {},
    consents: profile.consents || { ai_coaching: false, health_data: false, research: false },
  }
}

export default function ProfilePage() {
  const { isAuthenticated, profile, updateProfile } = useAuth()
  const location = useLocation()
  const savedForm = useMemo(() => buildForm(profile), [profile])
  const [draft, setDraft] = useState(null)
  const [editingAll, setEditingAll] = useState(false)
  const [editingSections, setEditingSections] = useState(() => new Set())
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [cycleContext, setCycleContext] = useState(null)

  const form = draft ?? savedForm
  const dirty = Boolean(draft && savedForm && !formsEqual(draft, savedForm))
  const isEditing = editingAll || editingSections.size > 0

  const blocker = useBlocker(
    ({ currentLocation, nextLocation }) =>
      dirty && currentLocation.pathname !== nextLocation.pathname,
  )

  useEffect(() => {
    if (!savedForm?.cycle_tracking_enabled) return undefined
    let cancelled = false
    getCycleContext()
      .then((result) => {
        if (!cancelled) setCycleContext(result)
      })
      .catch(() => {
        if (!cancelled) setCycleContext(null)
      })
    return () => {
      cancelled = true
    }
  }, [savedForm?.cycle_tracking_enabled])

  useEffect(() => {
    if (!dirty) return undefined
    function onBeforeUnload(event) {
      event.preventDefault()
      event.returnValue = ''
    }
    window.addEventListener('beforeunload', onBeforeUnload)
    return () => window.removeEventListener('beforeunload', onBeforeUnload)
  }, [dirty])

  useEffect(() => {
    if (!savedForm) return
    const section = sectionFromHash(location.hash)
    if (section) {
      window.setTimeout(() => scrollToProfileSection(section), 80)
    }
  }, [savedForm, location.hash])

  const missing = useMemo(() => (form ? missingCompletenessItems(form) : []), [form])
  const profileComplete = missing.length === 0

  if (!isAuthenticated) return <Navigate to="/signin" replace />
  if (!form) {
    return (
      <AppShell title="Profile">
        <p className="text-sm text-[var(--aal-muted)]">Loading profile...</p>
      </AppShell>
    )
  }

  function isSectionEditing(id) {
    return editingAll || editingSections.has(id)
  }

  function startSectionEdit(id) {
    setMessage('')
    setEditingSections((prev) => new Set(prev).add(id))
  }

  function startAllEdit() {
    setMessage('')
    setEditingAll(true)
  }

  function stopEditing() {
    setEditingAll(false)
    setEditingSections(new Set())
  }

  function discardChanges() {
    setDraft(null)
    setError('')
    setMessage('')
    stopEditing()
  }

  function updateField(key, value) {
    setDraft((prev) => ({ ...(prev ?? savedForm), [key]: value }))
    setMessage('')
  }

  function jumpToSection(sectionId, { edit = false } = {}) {
    if (edit) startSectionEdit(sectionId)
    window.setTimeout(() => scrollToProfileSection(sectionId), 30)
  }

  async function handleSave(event) {
    event?.preventDefault()
    if (!dirty) {
      stopEditing()
      return
    }
    setSaving(true)
    setError('')
    setMessage('')
    try {
      const updated = await updateProfile({
        name: form.name,
        primary_goal: toTextOrNull(form.primary_goal),
        secondary_goal: toTextOrNull(form.secondary_goal),
        equipment: toTextOrNull(form.equipment),
        days_per_week: toNumberOrNull(form.days_per_week),
        workout_duration_minutes: toNumberOrNull(form.workout_duration_minutes),
        preferred_workout_time: toTextOrNull(form.preferred_workout_time),
        injuries_limitations: toTextOrNull(form.injuries_limitations),
        fitness_level: toTextOrNull(form.fitness_level),
        exercises_hate: toTextOrNull(form.exercises_hate),
        exercises_love: toTextOrNull(form.exercises_love),
        sex: toTextOrNull(form.sex),
        date_of_birth: toTextOrNull(form.date_of_birth),
        height_cm: toNumberOrNull(form.height_cm),
        weight: toNumberOrNull(form.weight) ?? undefined,
        units: form.units === 'imperial' ? 'imperial' : 'metric',
        training_history_months: toNumberOrNull(form.training_history_months),
        current_weekly_volume: form.current_weekly_volume || {},
        longest_recent_session: toTextOrNull(form.longest_recent_session),
        race_prs: toTextOrNull(form.race_prs),
        weekly_minutes_budget: toNumberOrNull(form.weekly_minutes_budget),
        goal_event_name: toTextOrNull(form.goal_event_name),
        goal_event_date: toTextOrNull(form.goal_event_date),
        goal_metric: toTextOrNull(form.goal_metric),
        ftp_watts: toNumberOrNull(form.ftp_watts),
        lthr_bpm: toNumberOrNull(form.lthr_bpm),
        max_hr_bpm: toNumberOrNull(form.max_hr_bpm),
        sports: form.sports || [],
        injuries: form.injuries || [],
      })
      const next = buildForm(updated?.profile)
      if (!next) throw new Error('Profile did not update.')
      setDraft(null)
      stopEditing()
      setMessage('Saved. Your coach will use this on the next plan.')
    } catch (err) {
      setError(err.message || 'Failed to save profile.')
    } finally {
      setSaving(false)
    }
  }

  function renderFields(fields, columns = 'md:grid-cols-2') {
    return (
      <div className={`grid gap-6 ${columns}`}>
        {fields.map((field) => (
          <div
            key={field.key}
            className={
              field.type === 'chips-single' ||
              field.type === 'chips-multi' ||
              field.type === 'textarea' ||
              field.type === 'weekly-volume'
                ? 'md:col-span-2'
                : ''
            }
          >
            <OnboardingField
              field={field}
              answers={form}
              value={form[field.key]}
              onChange={(value) => updateField(field.key, value)}
            />
          </div>
        ))}
      </div>
    )
  }

  return (
    <AppShell title="Profile">
      <form onSubmit={handleSave} className={`w-full space-y-8 ${isEditing ? 'pb-28' : ''}`}>
        <PageHeader
          eyebrow="Athlete"
          title="Profile"
          subtitle="Your training identity — the snapshot your coach reads before it writes a plan."
          actions={
            <button
              type="button"
              onClick={startAllEdit}
              disabled={editingAll}
              className="inline-flex items-center gap-2 rounded-xl bg-sage px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-60"
            >
              <Pencil className="h-4 w-4" />
              {editingAll ? 'Editing' : 'Edit profile'}
            </button>
          }
        />

        <motion.section
          id="profile-identity"
          initial="hidden"
          animate="show"
          variants={fadeUp}
          className="scroll-mt-24 overflow-hidden rounded-3xl border border-[var(--aal-line)] bg-[var(--aal-card)]"
        >
          <div className="flex flex-col gap-6 p-6 sm:flex-row sm:items-start sm:p-8">
            <div className="relative shrink-0">
              <div className="absolute -left-3 top-3 hidden h-[calc(100%-1.5rem)] w-1 rounded-full bg-sage sm:block" />
              <UserAvatar letter={form.avatar_letter} name={form.name} size="xl" />
            </div>
            <div className="min-w-0 flex-1">
              {isSectionEditing('identity') ? (
                <IdentityEditFields form={form} onChange={updateField}>
                  <OnboardingField
                    field={{ key: 'sports', label: 'Sports', type: 'sports' }}
                    answers={form}
                    value={form.sports}
                    onChange={(value) => updateField('sports', value)}
                  />
                </IdentityEditFields>
              ) : (
                <>
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <h2 className="font-display text-4xl font-medium tracking-tight text-[var(--aal-ink)] sm:text-5xl">
                      {form.name || 'Athlete'}
                    </h2>
                    <SectionEditButton
                      editing={false}
                      onEdit={() => startSectionEdit('identity')}
                    />
                  </div>
                  <div className="mt-4">
                    <SportPills sports={form.sports} />
                  </div>
                  <IdentityFocus form={form} />
                </>
              )}

              <div className="mt-6 max-w-md">
                {profileComplete ? (
                  <p className="text-sm font-medium text-sage">Profile completed</p>
                ) : (
                  <MissingCompleteness
                    items={missing}
                    onJump={(item) => jumpToSection(item.section, { edit: true })}
                  />
                )}
              </div>
            </div>
          </div>
        </motion.section>

        <JumpNav onJump={(id) => jumpToSection(id)} />

        <FactStrip form={{ ...form, displayAge: displayAge(form) }} />

        <motion.div initial="hidden" animate="show" variants={fadeUp} style={{ animationDelay: '80ms' }}>
          <SectionCard
            id="profile-training"
            title="Training"
            subtitle="Goals, fitness, and the week you can actually keep."
            actions={
              <SectionEditButton
                editing={isSectionEditing('training')}
                onEdit={() => startSectionEdit('training')}
              />
            }
          >
            {isSectionEditing('training') ? (
              <div className="space-y-8">
                <div>
                  <h3 className="mb-4 text-sm font-semibold uppercase tracking-[0.14em] text-[var(--aal-muted)]">
                    Goal
                  </h3>
                  {renderFields(GOAL_FIELDS)}
                </div>
                <div>
                  <h3 className="mb-4 text-sm font-semibold uppercase tracking-[0.14em] text-[var(--aal-muted)]">
                    Fitness
                  </h3>
                  {renderFields(FITNESS_FIELDS)}
                </div>
                <div>
                  <h3 className="mb-4 text-sm font-semibold uppercase tracking-[0.14em] text-[var(--aal-muted)]">
                    Physiology
                  </h3>
                  {renderFields(PHYSIOLOGY_FIELDS)}
                </div>
                <div>
                  <h3 className="mb-4 text-sm font-semibold uppercase tracking-[0.14em] text-[var(--aal-muted)]">
                    Weekly time
                  </h3>
                  {renderFields(TIME_FIELDS)}
                </div>
              </div>
            ) : (
              <TrainingView
                form={form}
                middleContent={<ProfileEventsPanel inTraining />}
              />
            )}
          </SectionCard>
        </motion.div>

        <SectionCard
          id="profile-body"
          title="Body"
          subtitle="Used for load, pacing, and unit display."
          actions={
            <SectionEditButton
              editing={isSectionEditing('body')}
              onEdit={() => startSectionEdit('body')}
            />
          }
        >
          {isSectionEditing('body') ? (
            <div className="space-y-6">
              {renderFields(BODY_FIELDS)}
              <MeasureFields form={form} onChange={updateField} />
            </div>
          ) : (
            <BodyView form={form} />
          )}
        </SectionCard>

        <SectionCard
          id="profile-health"
          title="Health"
          subtitle="Injuries and limits the coach should train around."
          actions={
            <SectionEditButton
              editing={isSectionEditing('health')}
              onEdit={() => startSectionEdit('health')}
            />
          }
        >
          {isSectionEditing('health') ? (
            <div>
              <OnboardingField
                field={{ key: 'injuries', type: 'injuries' }}
                answers={form}
                value={form.injuries}
                onChange={(value) => updateField('injuries', value)}
              />
              <div className="mt-6">
                <OnboardingField
                  field={{
                    key: 'injuries_limitations',
                    label: 'Anything else to avoid',
                    type: 'textarea',
                  }}
                  answers={form}
                  value={form.injuries_limitations}
                  onChange={(value) => updateField('injuries_limitations', value)}
                />
              </div>
              <CycleTrackingFields
                form={form}
                onChange={updateField}
                onCycleUpdate={setCycleContext}
              />
            </div>
          ) : (
            <>
              <HealthView form={form} />
              <div className="mt-6">
                <CycleTrackingView form={form} cycleContext={cycleContext} />
              </div>
            </>
          )}
        </SectionCard>

        <SectionCard
          id="profile-preferences"
          title="Preferences"
          subtitle="What you can train with, and what you actually enjoy."
          actions={
            <SectionEditButton
              editing={isSectionEditing('preferences')}
              onEdit={() => startSectionEdit('preferences')}
            />
          }
        >
          {isSectionEditing('preferences') ? (
            renderFields(PREFERENCE_FIELDS)
          ) : (
            <PreferencesView form={form} />
          )}
        </SectionCard>

        <SettingsHint />

        {isEditing ? (
          <StickySaveBar
            dirty={dirty}
            saving={saving}
            message={message}
            error={error}
            onDone={stopEditing}
            onDiscard={discardChanges}
          />
        ) : message ? (
          <p className="text-sm text-sage">{message}</p>
        ) : null}
      </form>

      <LeaveGuard
        open={blocker.state === 'blocked'}
        onStay={() => blocker.reset?.()}
        onLeave={() => blocker.proceed?.()}
      />
    </AppShell>
  )
}
