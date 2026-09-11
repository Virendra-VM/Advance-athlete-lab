import assert from 'node:assert/strict'
import { describe, it } from 'vitest'
import {
  acwrMarkerPercent,
  hasLoadHistory,
  interpretLoad,
  isSparseBaseline,
  weeksWithDistance,
} from './loadGuides.js'

describe('loadGuides', () => {
  it('interpretLoad asks for baseline when chronic is missing', () => {
    const result = interpretLoad({ acwr: null, acuteKm: 20, chronicKm: 0 })
    assert.equal(result.zone.id, 'empty')
    assert.match(result.headline, /usual week/i)
  })

  it('interpretLoad uses sweet-spot copy inside the productive band', () => {
    const result = interpretLoad({ acwr: 1.1, acuteKm: 40, chronicKm: 36 })
    assert.equal(result.zone.id, 'sweet')
    assert.match(result.headline, /useful pace/i)
    assert.ok(result.actions.length >= 1)
  })

  it('acwrMarkerPercent clamps onto the 0–2 gauge', () => {
    assert.equal(acwrMarkerPercent(null), null)
    assert.equal(acwrMarkerPercent(1), 50)
    assert.equal(acwrMarkerPercent(3), 100)
    assert.equal(acwrMarkerPercent(-1), 0)
  })

  it('history helpers detect sparse baselines', () => {
    const sparse = {
      acute_load_km: 0,
      chronic_load_km: 0,
      weekly_volume_history: [
        { total_distance_km: 10 },
        { total_distance_km: 0 },
        { total_distance_km: 12 },
      ],
    }
    assert.equal(hasLoadHistory(sparse), true)
    assert.equal(weeksWithDistance(sparse), 2)
    assert.equal(isSparseBaseline(sparse), true)
  })
})
