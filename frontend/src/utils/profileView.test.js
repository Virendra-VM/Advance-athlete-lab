import assert from 'node:assert/strict'
import { describe, it } from 'vitest'
import {
  ageFromDob,
  cmToInches,
  inchesToCm,
  isEmptyValue,
  kgToLb,
  lbToKg,
  toNumberOrNull,
} from './profileView.js'

describe('profileView helpers', () => {
  it('isEmptyValue covers blanks and empty collections', () => {
    assert.equal(isEmptyValue(null), true)
    assert.equal(isEmptyValue('  '), true)
    assert.equal(isEmptyValue([]), true)
    assert.equal(isEmptyValue({}), true)
    assert.equal(isEmptyValue('ready'), false)
  })

  it('toNumberOrNull parses finite numbers only', () => {
    assert.equal(toNumberOrNull(''), null)
    assert.equal(toNumberOrNull('12.5'), 12.5)
    assert.equal(toNumberOrNull('nope'), null)
  })

  it('unit conversions round to display precision', () => {
    assert.equal(cmToInches(182.88), 72)
    assert.equal(inchesToCm(72), 182.9)
    assert.equal(kgToLb(70), 154.3)
    assert.equal(lbToKg(154.3), 70)
  })

  it('ageFromDob returns whole years', () => {
    assert.equal(ageFromDob(null), null)
    const dob = new Date()
    dob.setFullYear(dob.getFullYear() - 30)
    dob.setMonth(0, 1)
    assert.equal(ageFromDob(dob.toISOString().slice(0, 10)), 30)
  })
})
