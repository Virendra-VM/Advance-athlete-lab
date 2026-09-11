import assert from 'node:assert/strict'
import { describe, it } from 'vitest'
import {
  ONBOARDING_STEPS,
  buildConfirmationMessage,
  buildOnboardingPayload,
  defaultAnswers,
  isStepComplete,
  primarySports,
} from './onboardingSteps.js'

describe('onboardingSteps', () => {
  it('primarySports excludes secondary entries', () => {
    assert.deepEqual(
      primarySports({
        sports: [
          { sport: 'Running', priority: 'primary' },
          { sport: 'Yoga / Mobility', priority: 'secondary' },
        ],
      }).map((entry) => entry.sport),
      ['Running'],
    )
  })

  it('isStepComplete requires only marked fields', () => {
    const body = ONBOARDING_STEPS.find((step) => step.id === 'body')
    assert.equal(isStepComplete(body, { name: 'Alex' }), false)
    assert.equal(
      isStepComplete(body, {
        name: 'Alex',
        sex: 'female',
        date_of_birth: '1994-01-01',
        height_cm: 170,
        weight: 60,
        units: 'metric',
      }),
      true,
    )
  })

  it('buildOnboardingPayload applies defaults and cleans values', () => {
    const payload = buildOnboardingPayload({
      ...defaultAnswers({ name: 'Alex', units: 'imperial' }),
      primary_goal: '  Marathon  ',
      days_per_week: '4',
      workout_duration_minutes: '60',
      sports: [{ sport: 'Running', priority: 'primary', experience_level: 'Intermediate' }],
      injuries: [{ body_region: 'Knee', status: 'active', severity: 'mild' }],
      consents: { ai_coaching: true },
      current_weekly_volume: { Running: '40' },
    })

    assert.equal(payload.name, 'Alex')
    assert.equal(payload.units, 'imperial')
    assert.equal(payload.primary_goal, 'Marathon')
    assert.equal(payload.days_per_week, 4)
    assert.equal(payload.weekly_minutes_budget, 240)
    assert.equal(payload.sports[0].sport, 'Running')
    assert.equal(payload.injuries[0].status, 'active')
    assert.equal(payload.consents.ai_coaching, true)
    assert.deepEqual(payload.current_weekly_volume, { Running: '40' })
  })

  it('buildConfirmationMessage summarizes the intake', () => {
    const message = buildConfirmationMessage({
      sports: [{ sport: 'Running', priority: 'primary' }],
      days_per_week: 4,
      workout_duration_minutes: 60,
      primary_goal: 'a marathon',
      injuries: [{ body_region: 'Knee' }],
    })
    assert.match(message, /Running toward a marathon/)
    assert.match(message, /4 days a week/)
    assert.match(message, /1 injury note on file/)
  })
})
