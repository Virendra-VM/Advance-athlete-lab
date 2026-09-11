import assert from 'node:assert/strict'
import { describe, it } from 'vitest'
import {
  buildRecoveryShiftMessage,
  buildWeekCommitMessage,
  buildWeekReviewMessage,
} from './weekPlanFlow.js'

describe('weekPlanFlow', () => {
  it('buildWeekReviewMessage includes phase context and review-only instruction', () => {
    const message = buildWeekReviewMessage(
      {
        season: {
          has_plan: true,
          week_in_phase: 2,
          current_phase: { phase_type: 'build', week_count: 6, intent: 'threshold' },
          week_intent: {
            focus: 'threshold',
            volume_bias: 'steady',
            intensity_bias: 'moderate',
            long_session_allowed_min: 90,
            events: [{ priority: 'B', name: 'Local 10k', date: '2024-07-01' }],
          },
        },
      },
      'No Tuesday AM',
    )

    assert.match(message, /Phase: Build \(week 2 of 6\)/)
    assert.match(message, /Long day up to: 90 min/)
    assert.match(message, /B-race Local 10k on 2024-07-01/)
    assert.match(message, /No Tuesday AM/)
    assert.match(message, /do not build the week table yet/i)
  })

  it('buildWeekReviewMessage falls back when only A-race exists', () => {
    const message = buildWeekReviewMessage({
      season: { a_race: { name: 'IM Arizona', date: '2024-11-17' } },
    })
    assert.match(message, /A-race: IM Arizona on 2024-11-17/)
    assert.match(message, /not specified/)
  })

  it('buildWeekCommitMessage asks for the full week table', () => {
    const message = buildWeekCommitMessage({}, 'Travel Friday')
    assert.match(message, /Plan my week now/)
    assert.match(message, /full week table/)
    assert.match(message, /Constraints to honour:\nTravel Friday/)
  })

  it('buildRecoveryShiftMessage includes range and optional notes', () => {
    const withRange = buildRecoveryShiftMessage(
      { start_date: '2024-08-05', end_date: '2024-08-11' },
      'Race moved up',
    )
    assert.match(withRange, /2024-08-05 → 2024-08-11/)
    assert.match(withRange, /Race moved up/)

    const fallback = buildRecoveryShiftMessage(null)
    assert.match(fallback, /this recovery block/)
  })
})
