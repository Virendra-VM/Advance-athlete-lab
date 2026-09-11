import assert from 'node:assert/strict'
import { beforeEach, describe, it } from 'vitest'
import {
  clearWeekFlowState,
  loadComposerDraft,
  loadComposerStorage,
  saveComposerDraft,
  saveWeekFlowState,
} from './coachComposerStorage.js'

function installMemorySessionStorage() {
  const store = new Map()
  globalThis.sessionStorage = {
    getItem(key) {
      return store.has(key) ? store.get(key) : null
    },
    setItem(key, value) {
      store.set(String(key), String(value))
    },
    removeItem(key) {
      store.delete(key)
    },
    clear() {
      store.clear()
    },
  }
}

describe('coachComposerStorage', () => {
  beforeEach(() => {
    installMemorySessionStorage()
  })

  it('returns null / empty without a profile id', () => {
    assert.equal(loadComposerStorage(null), null)
    assert.equal(loadComposerDraft(''), '')
    saveComposerDraft(null, 'ignored')
    assert.equal(sessionStorage.getItem('aal_coach_composer_anon'), null)
  })

  it('persists and reloads drafts without clobbering week flow', () => {
    saveWeekFlowState('p1', {
      weekFlowStep: 'review',
      weekConstraints: 'No hills',
      recoveryShift: true,
      recoveryPhase: { phase_type: 'recovery_week' },
    })
    saveComposerDraft('p1', 'draft text')

    assert.equal(loadComposerDraft('p1'), 'draft text')
    const stored = loadComposerStorage('p1')
    assert.equal(stored.weekFlowStep, 'review')
    assert.equal(stored.weekConstraints, 'No hills')
    assert.equal(stored.recoveryShift, true)
    assert.deepEqual(stored.recoveryPhase, { phase_type: 'recovery_week' })
  })

  it('clearWeekFlowState resets flow fields but keeps draft', () => {
    saveComposerDraft('p1', 'keep me')
    saveWeekFlowState('p1', {
      weekFlowStep: 'commit',
      weekConstraints: 'Travel',
      recoveryShift: true,
      recoveryPhase: { id: 1 },
    })
    clearWeekFlowState('p1')

    const stored = loadComposerStorage('p1')
    assert.equal(stored.draft, 'keep me')
    assert.equal(stored.weekFlowStep, null)
    assert.equal(stored.weekConstraints, '')
    assert.equal(stored.recoveryShift, false)
    assert.equal(stored.recoveryPhase, null)
  })

  it('tolerates corrupt JSON in sessionStorage', () => {
    sessionStorage.setItem('aal_coach_composer_p1', '{not-json')
    assert.equal(loadComposerStorage('p1'), null)
    assert.equal(loadComposerDraft('p1'), '')
  })
})
