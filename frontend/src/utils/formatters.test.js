import assert from 'node:assert/strict'
import { describe, it } from 'vitest'
import {
  addDaysISO,
  formatDistanceKm,
  formatDuration,
  formatDurationHours,
  parseUtcDate,
  toISODateLocal,
} from './formatters.js'

describe('formatters', () => {
  it('formatDistanceKm converts meters and handles null', () => {
    assert.equal(formatDistanceKm(null), '—')
    assert.equal(formatDistanceKm(5234), '5.23 km')
    assert.equal(formatDistanceKm(0), '0.00 km')
  })

  it('parseUtcDate treats naive timestamps as UTC', () => {
    assert.equal(parseUtcDate(null), null)
    assert.equal(parseUtcDate(''), null)
    assert.equal(parseUtcDate('2024-06-15').toISOString(), '2024-06-15T00:00:00.000Z')
    assert.equal(parseUtcDate('2024-06-15T08:30:00').toISOString(), '2024-06-15T08:30:00.000Z')
    assert.equal(parseUtcDate('2024-06-15 08:30:00').toISOString(), '2024-06-15T08:30:00.000Z')
    assert.equal(parseUtcDate('2024-06-15T08:30:00Z').toISOString(), '2024-06-15T08:30:00.000Z')
    assert.ok(parseUtcDate(1718438400000) instanceof Date)
  })

  it('formatDuration renders h:mm:ss and m:ss', () => {
    assert.equal(formatDuration(null), '—')
    assert.equal(formatDuration(NaN), '—')
    assert.equal(formatDuration(65), '1:05')
    assert.equal(formatDuration(3661), '1:01:01')
    assert.equal(formatDuration(-5), '0:00')
  })

  it('formatDurationHours shows one decimal hour', () => {
    assert.equal(formatDurationHours(3600), '1.0h')
    assert.equal(formatDurationHours(5400), '1.5h')
  })

  it('toISODateLocal and addDaysISO stay calendar-stable', () => {
    assert.equal(toISODateLocal(new Date(2024, 0, 5)), '2024-01-05')
    assert.equal(addDaysISO('2024-01-31', 1), '2024-02-01')
    assert.equal(addDaysISO('2024-02-28', 1), '2024-02-29')
  })
})
