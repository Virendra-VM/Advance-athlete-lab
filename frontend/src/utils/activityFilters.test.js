import assert from 'node:assert/strict'
import { describe, it } from 'vitest'
import {
  collectSportOptions,
  filterHistoryActivities,
  filterOverviewActivities,
} from './activityFilters.js'

const activities = [
  {
    name: 'Morning Run',
    sport_type: 'Run',
    activity_date: '2024-06-10T07:00:00Z',
    distance_m: 10000,
    average_heartrate: 145,
  },
  {
    name: 'Easy Ride',
    sport_type: 'Ride',
    activity_date: '2024-05-01T07:00:00Z',
    distance_m: 40000,
    average_heartrate: null,
  },
  {
    name: 'Trail Run',
    sport_type: 'TrailRun',
    activity_date: '2024-06-12T07:00:00Z',
    distance_m: 8000,
    average_heartrate: 150,
  },
]

describe('activityFilters', () => {
  it('collectSportOptions dedupes formatted sports', () => {
    assert.deepEqual(collectSportOptions(activities), ['All sports', 'Bike', 'Run'])
  })

  it('filterOverviewActivities filters by sport label', () => {
    const rows = filterOverviewActivities(activities, { period: 'all', sport: 'Bike' })
    assert.equal(rows.length, 1)
    assert.equal(rows[0].name, 'Easy Ride')
  })

  it('filterHistoryActivities searches, filters HR, and sorts by distance', () => {
    const rows = filterHistoryActivities(activities, {
      search: 'run',
      sport: 'All sports',
      dateFrom: '2024-06-01',
      dateTo: '2024-06-30',
      minDistanceKm: 9,
      hasHr: 'with',
      sort: 'distance_desc',
    })
    assert.equal(rows.length, 1)
    assert.equal(rows[0].name, 'Morning Run')
  })

  it('filterHistoryActivities sorts oldest first when requested', () => {
    const rows = filterHistoryActivities(activities, {
      search: '',
      sport: 'All sports',
      sort: 'date_asc',
    })
    assert.equal(rows[0].name, 'Easy Ride')
    assert.equal(rows[rows.length - 1].name, 'Trail Run')
  })
})
