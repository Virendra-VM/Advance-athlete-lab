import assert from 'node:assert/strict'
import { describe, it } from 'vitest'
import { buildProfileSavePayload } from './profileForm.js'
import { formsEqual } from './profileView.js'

describe('clinical baseline profile fields', () => {
  it('sends occlusion pressure and basal temperature on save', () => {
    const payload = buildProfileSavePayload({
      name: 'Asha',
      units: 'metric',
      sports: [],
      injuries: [],
      aop_mmhg: '180',
      basal_body_temp_c: '36.6',
      cycle_tracking_enabled: true,
      cycle_length_manual: '28',
    })
    assert.equal(payload.aop_mmhg, 180)
    assert.equal(payload.basal_body_temp_c, 36.6)
    assert.equal(payload.cycle_length_manual, 28)
  })

  it('treats a blank baseline as cleared, and a filled one as a real edit', () => {
    const saved = { aop_mmhg: 180, basal_body_temp_c: 36.5, units: 'metric' }
    const cleared = { ...saved, aop_mmhg: '', basal_body_temp_c: '' }
    assert.equal(formsEqual(saved, cleared), false)
    const payload = buildProfileSavePayload({
      ...cleared,
      name: 'Asha',
      sports: [],
      injuries: [],
    })
    assert.equal(payload.aop_mmhg, null)
    assert.equal(payload.basal_body_temp_c, null)
  })
})
