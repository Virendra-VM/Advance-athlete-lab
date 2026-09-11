import assert from 'node:assert/strict'
import { describe, it } from 'vitest'
import { getAcwrZone } from './statusColors.js'

describe('getAcwrZone', () => {
  it('maps ACWR bands to athlete-facing zones', () => {
    assert.equal(getAcwrZone(null).id, 'empty')
    assert.equal(getAcwrZone(0.7).id, 'recovery')
    assert.equal(getAcwrZone(0.8).id, 'sweet')
    assert.equal(getAcwrZone(1.3).id, 'sweet')
    assert.equal(getAcwrZone(1.4).id, 'caution')
    assert.equal(getAcwrZone(1.5).id, 'caution')
    assert.equal(getAcwrZone(1.51).id, 'high')
  })
})
