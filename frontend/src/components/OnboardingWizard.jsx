import { useMemo, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { ArrowLeft, ArrowRight, Sparkles } from 'lucide-react'
import { Navigate, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { pagePaddingClass, pageShellClass } from '../utils/statusColors'
import { buildConfirmationMessage, ONBOARDING_STEPS } from '../utils/onboardingSteps'
import Navigation from './Navigation'
import Card from './ui/Card'

function Chip({ label, selected, onClick }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-full border px-4 py-2 text-sm font-medium transition-colors ${
        selected
          ? 'border-sage bg-sage text-white'
          : 'border-slate-200 bg-white text-slate-700 dark:border-white/10 dark:bg-gray-800 dark:text-slate-200'
      }`}
    >
      {label}
    </button>
  )
}

function StepInput({ step, value, onChange }) {
  if (step.type === 'textarea') {
    return (
      <textarea
        value={value}
        onChange={(e) => onChange(e.target.value)}
        rows={4}
        placeholder={step.hint || 'Type your answer...'}
        className="mt-6 w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-slate-900 outline-none ring-sage focus:ring-2 dark:border-white/10 dark:bg-gray-900 dark:text-white"
      />
    )
  }

  if (step.type === 'chips-single') {
    return (
      <div className="mt-6 flex flex-wrap gap-3">
        {step.options.map((option) => {
          const label = step.optionLabels?.[option] || option
          return (
            <Chip
              key={option}
              label={label}
              selected={String(value) === String(option)}
              onClick={() => onChange(option)}
            />
          )
        })}
      </div>
    )
  }

  if (step.type === 'chips-multi') {
    const selected = value ? value.split(', ').filter(Boolean) : []
    function toggle(option) {
      const next = selected.includes(option)
        ? selected.filter((item) => item !== option)
        : [...selected, option]
      onChange(next.join(', '))
    }
    return (
      <div className="mt-6 flex flex-wrap gap-3">
        {step.options.map((option) => (
          <Chip
            key={option}
            label={option}
            selected={selected.includes(option)}
            onClick={() => toggle(option)}
          />
        ))}
      </div>
    )
  }

  return null
}

export default function OnboardingWizard() {
  const navigate = useNavigate()
  const { isAuthenticated, needsOnboarding, submitOnboarding, profile } = useAuth()
  const [stepIndex, setStepIndex] = useState(0)
  const [answers, setAnswers] = useState({})
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [showConfirm, setShowConfirm] = useState(false)

  const totalSteps = ONBOARDING_STEPS.length
  const step = ONBOARDING_STEPS[stepIndex]
  const progress = showConfirm ? 100 : ((stepIndex + 1) / totalSteps) * 100

  const currentValue = answers[step?.field] ?? ''

  const canContinue = useMemo(() => {
    if (showConfirm) return true
    if (!step?.required) return true
    return Boolean(String(currentValue).trim())
  }, [showConfirm, step, currentValue])

  if (!isAuthenticated) return <Navigate to="/signin" replace />
  if (!needsOnboarding && profile?.onboarding_completed) {
    return <Navigate to="/connect-strava" replace />
  }

  function updateAnswer(value) {
    setAnswers((prev) => ({ ...prev, [step.field]: value }))
  }

  function appendSuggestion(text) {
    const existing = answers[step.field] || ''
    const next = existing ? `${existing}, ${text}` : text
    updateAnswer(next)
  }

  async function handleFinish() {
    setSubmitting(true)
    setError('')
    try {
      await submitOnboarding({
        primary_goal: answers.primary_goal,
        secondary_goal: answers.secondary_goal || null,
        equipment: answers.equipment,
        days_per_week: Number(answers.days_per_week),
        workout_duration_minutes: Number(answers.workout_duration_minutes),
        preferred_workout_time: answers.preferred_workout_time,
        injuries_limitations: answers.injuries_limitations || null,
        fitness_level: answers.fitness_level,
        exercises_hate: answers.exercises_hate || null,
        exercises_love: answers.exercises_love || null,
      })
      navigate('/connect-strava')
    } catch (err) {
      setError(err.message || 'Failed to save your answers.')
    } finally {
      setSubmitting(false)
    }
  }

  function handleNext() {
    if (stepIndex < totalSteps - 1) {
      setStepIndex((i) => i + 1)
      return
    }
    setShowConfirm(true)
  }

  function handleBack() {
    if (showConfirm) {
      setShowConfirm(false)
      return
    }
    if (stepIndex > 0) setStepIndex((i) => i - 1)
  }

  return (
    <div className={pageShellClass}>
      <Navigation subtitle="Let's get to know you" showProfileLink={false} />

      <main className={`${pagePaddingClass} mx-auto max-w-3xl`}>
        <div className="mb-8">
          <div className="mb-2 flex items-center justify-between text-sm text-slate-500">
            <span>{showConfirm ? 'All done!' : `Question ${stepIndex + 1} of ${totalSteps}`}</span>
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

        <Card className="overflow-hidden p-8">
          <AnimatePresence mode="wait">
            {!showConfirm ? (
              <motion.div
                key={step.id}
                initial={{ opacity: 0, x: 40 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -40 }}
                transition={{ duration: 0.3 }}
              >
                <p className="text-sm font-medium text-sage">Your coach is listening...</p>
                <h2 className="mt-2 text-2xl font-bold text-slate-900 dark:text-white">{step.title}</h2>
                <p className="mt-2 text-slate-500 dark:text-slate-400">{step.subtitle}</p>

                <StepInput step={step} value={currentValue} onChange={updateAnswer} />

                {step.options && step.type === 'textarea' && (
                  <div className="mt-4 flex flex-wrap gap-2">
                    {step.options.map((option) => (
                      <button
                        key={option}
                        type="button"
                        onClick={() => appendSuggestion(option)}
                        className="rounded-full border border-slate-200 px-3 py-1 text-xs text-slate-600 dark:border-white/10 dark:text-slate-300"
                      >
                        + {option}
                      </button>
                    ))}
                  </div>
                )}
              </motion.div>
            ) : (
              <motion.div
                key="confirm"
                initial={{ opacity: 0, scale: 0.98 }}
                animate={{ opacity: 1, scale: 1 }}
                className="text-center"
              >
                <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-sage/10 text-sage">
                  <Sparkles className="h-8 w-8" />
                </div>
                <h2 className="mt-6 text-2xl font-bold text-slate-900 dark:text-white">You're all set!</h2>
                <p className="mt-4 text-lg leading-relaxed text-slate-600 dark:text-slate-300">
                  {buildConfirmationMessage(answers)}
                </p>
                <p className="mt-4 text-sm text-slate-500">
                  Saved permanently. Update anytime from your profile or settings.
                </p>
              </motion.div>
            )}
          </AnimatePresence>

          {error && <p className="mt-4 text-sm text-danger-muted">{error}</p>}

          <div className="mt-8 flex items-center justify-between border-t border-slate-100 pt-6 dark:border-white/10">
            <button
              type="button"
              onClick={handleBack}
              disabled={stepIndex === 0 && !showConfirm}
              className="flex items-center gap-2 rounded-xl px-4 py-2 text-sm text-slate-600 disabled:opacity-40 dark:text-slate-300"
            >
              <ArrowLeft className="h-4 w-4" /> Back
            </button>

            {!showConfirm ? (
              <button
                type="button"
                onClick={handleNext}
                disabled={!canContinue}
                className="flex items-center gap-2 rounded-xl bg-sage px-6 py-3 font-semibold text-white disabled:opacity-40"
              >
                Continue <ArrowRight className="h-4 w-4" />
              </button>
            ) : (
              <button
                type="button"
                onClick={handleFinish}
                disabled={submitting}
                className="flex items-center gap-2 rounded-xl bg-sage px-6 py-3 font-semibold text-white disabled:opacity-40"
              >
                {submitting ? 'Saving...' : "Let's go"} <ArrowRight className="h-4 w-4" />
              </button>
            )}
          </div>
        </Card>
      </main>
    </div>
  )
}
