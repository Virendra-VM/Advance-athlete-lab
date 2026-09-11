import assert from 'node:assert/strict'
import { describe, it } from 'vitest'
import { dailyMarkerPercent, dailyRatio, getDailyZone } from './dailyGuides.js'

describe('dailyGuides', () => {
  it('dailyRatio guards missing or zero usual', () => {
    assert.equal(dailyRatio(null, 8000), null)
    assert.equal(dailyRatio(8000, 0), null)
    assert.equal(dailyRatio(9000, 9000), 1)
  })

  it('dailyMarkerPercent maps ratio onto the daily scale', () => {
    assert.equal(dailyMarkerPercent(null), null)
    assert.equal(dailyMarkerPercent(0.5), 0)
    assert.equal(dailyMarkerPercent(1.8), 100)
  })

  it('getDailyZone treats sedentary step counts specially', () => {
    assert.equal(getDailyZone(1.0, 2000).id, 'quiet')
    assert.equal(getDailyZone(null).id, 'empty')
    assert.equal(getDailyZone(1.0, 9000).id, 'typical')
    assert.equal(getDailyZone(1.4, 12000).id, 'busy')
    assert.equal(getDailyZone(1.6, 15000).id, 'high')
  })
})
