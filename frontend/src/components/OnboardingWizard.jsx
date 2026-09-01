import { useMemo, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { ArrowLeft, ArrowRight, Check, Sparkles } from 'lucide-react'
import { Navigate, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { pagePaddingClass, pageShellClass } from '../utils/statusColors'
import {
  buildConfirmationMessage,
  buildOnboardingPayload,
  defaultAnswers,
  isStepComplete,
  ONBOARDING_STEPS,
  primarySports,
} from '../utils/onboardingSteps'
import Navigation from './Navigation'
import Card from './ui/Card'
import OnboardingField from './onboarding/OnboardingFields'

function ReviewSummary({ answers }) {
  const sports = primarySports(answers)
    .map((entry) => `${entry.sport} (${entry.experience_level || 'beginner'})`)
    .join(', ')

  const rows = [
    ['Sports', sports || 'Not set'],
    ['Goal', answers.primary_goal || 'Not set'],
    [
      'Event',
      answers.goal_event_name
        ? `${answers.goal_event_name}${answers.goal_event_date ? ` · ${answers.goal_event_date}` : ''}`
        : 'None',
    ],
    ['Fitness level', answers.fitness_level || 'Not set'],
    [
      'Weekly time',
      answers.days_per_week
        ? `${answers.days_per_week} days · ${answers.workout_duration_minutes || '?'} min sessions`
        : 'Not set',
    ],
    ['Equipment', answers.equipment || 'Not set'],
    [
      'Injuries',
      (answers.injuries || []).length
        ? answers.injuries
            .map((entry) => `${entry.body_region}${entry.status === 'active' ? ' (ongoing)' : ''}`)
            .join(', ')
        : 'None reported',
    ],
  ]

  return (
    <div className="mb-8 overflow-hidden rounded-xl border border-[var(--aal-line)]">
      <dl className="divide-y divide-[var(--aal-line)] text-sm">
        {rows.map(([label, value]) => (
          <div key={label} className="flex flex-col gap-1 px-4 py-3 sm:flex-row sm:items-baseline sm:gap-4">
            <dt className="w-40 shrink-0 text-xs font-semibold uppercase tracking-wide text-[var(--aal-muted)]">
              {label}
            </dt>
            <dd className="min-w-0 flex-1">{value}</dd>
          </div>
        ))}
      </dl>
    </div>
  )
}

export default function OnboardingWizard() {
  const navigate = useNavigate()
  const { isAuthenticated, needsOnboarding, submitOnboarding, profile } = useAuth()
  const [stepIndex, setStepIndex] = useState(0)
  const [answers, setAnswers] = useState(() => defaultAnswers(profile))
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')

  const totalSteps = ONBOARDING_STEPS.length
  const step = ONBOARDING_STEPS[stepIndex]
  const isLastStep = stepIndex === totalSteps - 1
  const progress = ((stepIndex + 1) / totalSteps) * 100

  const canContinue = useMemo(() => isStepComplete(step, answers), [step, answers])

  if (!isAuthenticated) return <Navigate to="/signin" replace />
  if (!needsOnboarding && profile?.onboarding_completed) {
    return <Navigate to="/connect-strava" replace />
  }

  function updateField(key, value) {
    setAnswers((prev) => ({ ...prev, [key]: value }))
  }

  async function handleFinish() {
    setSubmitting(true)
    setError('')
    try {
      await submitOnboarding(buildOnboardingPayload(answers))
      navigate('/connect-strava')
    } catch (err) {
      setError(err.message || 'Failed to save your answers.')
    } finally {
      setSubmitting(false)
    }
  }

  function handleNext() {
    if (isLastStep) {
      handleFinish()
      return
    }
    setStepIndex((index) => index + 1)
  }

  function handleBack() {
    if (stepIndex > 0) setStepIndex((index) => index - 1)
  }

  return (
    <div className={pageShellClass}>
      <Navigation subtitle="Let's get to know you" showProfileLink={false} />

      <main className={`${pagePaddingClass} mx-auto max-w-3xl`}>
        <div className="mb-8">
          <div className="mb-2 flex items-center justify-between text-sm text-[var(--aal-muted)]">
            <span>
              Step {stepIndex + 1} of {totalSteps}
              {step.optional ? ' · optional' : ''}
            </span>
            <span>{Math.round(progress)}%</span>
          </div>
          <div className="h-2 overflow-hidden rounded-full bg-slate-200 dark:bg-gray-700">
            <motion.div
              className="h-full bg-sage"
              animate={{ width: `${progress}%` }}
              transition={{ duration: 0.4 }}
            />
          </div>
        </div>

        <Card className="overflow-hidden p-6 sm:p-8">
          <AnimatePresence mode="wait">
            <motion.div
              key={step.id}
              initial={{ opacity: 0, x: 32 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -32 }}
              transition={{ duration: 0.28 }}
            >
              <p className="text-sm font-medium text-sage">{step.eyebrow}</p>
              <h2 className="mt-2 text-2xl font-bold">{step.title}</h2>
              <p className="mt-2 text-[var(--aal-muted)]">{step.subtitle}</p>

              {step.type === 'intro' && (
                <div className="mt-8 space-y-3">
                  {step.bullets.map((bullet) => (
                    <div key={bullet} className="flex items-start gap-3 text-sm">
                      <Check className="mt-0.5 h-4 w-4 shrink-0 text-sage" />
                      <span>{bullet}</span>
                    </div>
                  ))}
                </div>
              )}

              {step.type === 'review' && (
                <div className="mt-8">
                  <div className="mb-6 flex items-start gap-3 rounded-xl bg-sage/10 p-4 text-sm">
                    <Sparkles className="mt-0.5 h-4 w-4 shrink-0 text-sage" />
                    <span>{buildConfirmationMessage(answers)}</span>
                  </div>
                  <ReviewSummary answers={answers} />
                </div>
              )}

              {step.fields.length > 0 && (
                <div className={`mt-8 grid gap-6 ${step.id === 'body' ? 'sm:grid-cols-2' : ''}`}>
                  {step.fields.map((field) => (
                    <div
                      key={field.key}
                      className={
                        step.id === 'body' && (field.type === 'chips-single' || field.key === 'name')
                          ? 'sm:col-span-2'
                          : ''
                      }
                    >
                      <OnboardingField
                        field={field}
                        answers={answers}
                        value={answers[field.key]}
                        onChange={(value) => updateField(field.key, value)}
                      />
                    </div>
                  ))}
                </div>
              )}
            </motion.div>
          </AnimatePresence>

          {error && <p className="mt-6 text-sm text-danger-muted">{error}</p>}

          <div className="mt-8 flex items-center justify-between gap-3 border-t border-[var(--aal-line)] pt-6">
            <button
              type="button"
              onClick={handleBack}
              disabled={stepIndex === 0}
              className="flex items-center gap-2 rounded-xl px-4 py-2 text-sm text-[var(--aal-muted)] disabled:opacity-40"
            >
              <ArrowLeft className="h-4 w-4" /> Back
            </button>

            <div className="flex items-center gap-3">
              {step.optional && !isLastStep && (
                <button
                  type="button"
                  onClick={() => setStepIndex((index) => index + 1)}
                  className="rounded-xl px-4 py-2 text-sm text-[var(--aal-muted)] underline-offset-4 hover:underline"
                >
                  Skip
                </button>
              )}
              <button
                type="button"
                onClick={handleNext}
                disabled={!canContinue || submitting}
                className="flex items-center gap-2 rounded-xl bg-sage px-6 py-3 font-semibold text-white disabled:opacity-40"
              >
                {isLastStep
                  ? submitting
                    ? 'Saving…'
                    : "Let's go"
                  : step.type === 'intro'
                    ? 'Start'
                    : 'Continue'}
                <ArrowRight className="h-4 w-4" />
              </button>
            </div>
          </div>
        </Card>

        <p className="mt-4 text-center text-xs text-[var(--aal-muted)]">
          Coaching guidance only — not medical advice. Everything saves to your profile and stays
          editable.
        </p>
      </main>
    </div>
  )
}
