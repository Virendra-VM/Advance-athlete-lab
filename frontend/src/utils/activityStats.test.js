import assert from 'node:assert/strict'
import { describe, it } from 'vitest'
import { computeActivityOverview, formatOverviewValue } from './activityStats.js'

describe('activityStats', () => {
  it('computeActivityOverview returns empty defaults', () => {
    const empty = computeActivityOverview([])
    assert.equal(empty.totalActivities, 0)
    assert.equal(empty.topSport, '—')
    assert.equal(empty.avgHeartRate, null)
  })

  it('computeActivityOverview aggregates distance, HR, and top sport', () => {
    const overview = computeActivityOverview([
      {
        sport_type: 'Run',
        distance_m: 10000,
        moving_time_s: 3600,
        average_heartrate: 140,
        max_heartrate: 170,
        activity_date: new Date().toISOString(),
      },
      {
        sport_type: 'VirtualRun',
        distance_m: 5000,
        moving_time_s: 1800,
        average_heartrate: 150,
        max_heartrate: 180,
        activity_date: '2020-01-01T00:00:00Z',
      },
      {
        sport_type: 'Ride',
        distance_m: 20000,
        moving_time_s: 3600,
        average_heartrate: null,
        max_heartrate: null,
        activity_date: '2020-01-02T00:00:00Z',
      },
    ])

    assert.equal(overview.totalActivities, 3)
    assert.equal(overview.totalDistanceKm, '35.0')
    assert.equal(overview.totalMovingHours, '2.5h')
    assert.equal(overview.avgHeartRate, 145)
    assert.equal(overview.maxHeartRate, 180)
    assert.equal(overview.topSport, 'Run')
    assert.equal(overview.topSportCount, 2)
    assert.equal(overview.activitiesThisWeek, 1)
    assert.equal(overview.longestDistanceKm, '20.0')
  })

  it('formatOverviewValue appends suffixes safely', () => {
    assert.equal(formatOverviewValue(null), '—')
    assert.equal(formatOverviewValue('—'), '—')
    assert.equal(formatOverviewValue(12, ' bpm'), '12 bpm')
  })
})
