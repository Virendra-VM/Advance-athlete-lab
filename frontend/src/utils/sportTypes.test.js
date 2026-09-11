import assert from 'node:assert/strict'
import { describe, it } from 'vitest'
import {
  formatSportType,
  getActivitySubtitle,
  getActivityTitle,
  getSportFamily,
  isGenericActivityName,
} from './sportTypes.js'

describe('sportTypes', () => {
  it('formatSportType maps Strava types to athlete labels', () => {
    assert.equal(formatSportType(null), 'Workout')
    assert.equal(formatSportType('VirtualRun'), 'Run')
    assert.equal(formatSportType('EBikeRide'), 'Bike')
    assert.equal(formatSportType('CustomSport'), 'Custom Sport')
  })

  it('getSportFamily normalizes aliases into families', () => {
    assert.equal(getSportFamily('TrailRun'), 'run')
    assert.equal(getSportFamily('VirtualRide'), 'ride')
    assert.equal(getSportFamily('WeightTraining'), 'strength')
    assert.equal(getSportFamily('OpenWaterSwim'), 'swim')
    assert.equal(getSportFamily('UnknownThing'), 'other')
  })

  it('activity titles hide generic Activity N names', () => {
    assert.equal(isGenericActivityName('Activity 12'), true)
    assert.equal(isGenericActivityName('Tempo hills'), false)
    assert.equal(getActivityTitle({ name: 'Activity 3', sport_type: 'Swim' }), 'Swim')
    assert.equal(getActivityTitle({ name: 'Tempo hills', sport_type: 'Run' }), 'Tempo hills')
    assert.equal(getActivitySubtitle({ name: 'Activity 3', sport_type: 'Swim' }), null)
    assert.equal(getActivitySubtitle({ name: 'Tempo hills', sport_type: 'Run' }), 'Run')
  })
})
