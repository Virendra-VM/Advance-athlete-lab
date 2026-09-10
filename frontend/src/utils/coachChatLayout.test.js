import assert from 'node:assert/strict'
import { describe, it } from 'node:test'
import {
  countWhatChangedItems,
  countWeekTableRows,
  extractDeepDiveBlocks,
  foldCoachContent,
  goDeeperPrompt,
  hasGoDeeperContent,
  messageHasScheduleContent,
  whatChangedSummary,
} from './coachChatLayout.js'

describe('coachChatLayout Phase 6', () => {
  it('folds WHAT CHANGED into expandable action block', () => {
    const content = `📊 **WHAT CHANGED**
• **FTP:** 232 W
• **Thursday:** zone targets updated

🟢 TODAY'S CALL
**Ready**`
    const folded = foldCoachContent(content)
    const what = folded.find((block) => block.type === 'whatChanged')
    assert.ok(what)
    assert.equal(what.itemCount, 2)
    assert.equal(what.summary, '2 things changed this week')
  })

  it('folds deep dive sections for go deeper chip', () => {
    const content = `🟢 TODAY'S CALL
**Ready**

**Why this works**
• ACWR 1.13 — one hard day max.`
    const folded = foldCoachContent(content)
    assert.equal(folded.some((block) => block.type === 'deepDive'), true)
    assert.equal(extractDeepDiveBlocks(folded).length, 1)
  })

  it('counts week table body rows', () => {
    const rows = [
      '| Day | Session |',
      '|---|---|',
      '| Monday | Rest |',
      '| Tuesday | Easy |',
    ]
    assert.equal(countWeekTableRows(rows), 2)
  })

  it('whatChangedSummary handles singular', () => {
    assert.equal(whatChangedSummary(1), '1 thing changed this week')
    assert.equal(whatChangedSummary(3), '3 things changed this week')
  })

  it('detects schedule content for go deeper', () => {
    assert.equal(messageHasScheduleContent('🗓️ REVISED WEEK\n| Day | Session |'), true)
    assert.equal(messageHasScheduleContent('Just a casual chat answer.'), false)
  })

  it('hasGoDeeperContent when deep dive or schedule present', () => {
    const schedule = foldCoachContent('📊 WHAT CHANGED\n• item\n🗓️ REVISED WEEK')
    assert.equal(hasGoDeeperContent(schedule, ''), true)
    const withWhy = foldCoachContent('**Why this works**\n• because')
    assert.equal(hasGoDeeperContent(withWhy, ''), true)
  })

  it('goDeeperPrompt adapts to what changed replies', () => {
    assert.match(goDeeperPrompt('📊 WHAT CHANGED\n• FTP'), /zone and session changes/)
    assert.match(goDeeperPrompt('Weekly plan ready'), /week's plan works/)
  })

  it('countWhatChangedItems ignores header only', () => {
    assert.equal(countWhatChangedItems(['📊 **WHAT CHANGED**']), 0)
    assert.equal(countWhatChangedItems(['📊 **WHAT CHANGED**', '• **FTP:** 232 W']), 1)
  })
})
