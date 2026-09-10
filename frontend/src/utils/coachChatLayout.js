/** Phase 6 — parse coach replies into mode-aware layout blocks. */

export function isTableLine(line) {
  const trimmed = String(line || '').trim()
  return trimmed.startsWith('|') && trimmed.endsWith('|') && trimmed.length > 2
}

export function isTableDivider(cells) {
  return (
    cells.length > 0 &&
    cells.every(
      (cell) => /^:?-{2,}:?$/.test(String(cell).replace(/\s/g, '')) || cell === '',
    )
  )
}

export function parseTableRow(line) {
  return String(line)
    .trim()
    .replace(/^\|/, '')
    .replace(/\|$/, '')
    .split('|')
    .map((cell) => cell.trim())
}

export function isRevisedWeekHeader(trimmed) {
  return /REVISED WEEK/i.test(trimmed) || /^🗓️\s/.test(trimmed)
}

export function todayCallTone(text) {
  if (/PRIMED\s*\/\s*ACCUMULATE/i.test(text)) return 'green'
  if (/CAUTION\s*\/\s*ABSORB/i.test(text)) return 'amber'
  if (/REST\s*\/\s*RESTORE/i.test(text)) return 'red'
  return null
}

export function isTodayCallHeader(trimmed) {
  return /TODAY'S CALL/i.test(trimmed)
}

export function isLockerHeader(trimmed) {
  return /LOCKER ROOM DIRECTIVE/i.test(trimmed) || /^🗣️\s+DIRECTIVE/i.test(trimmed)
}

export function isWhatChangedHeader(trimmed) {
  return /WHAT CHANGED/i.test(trimmed)
}

export function isDeepDiveHeader(trimmed) {
  return /^\*\*Why (this works|recovery)\*\*/i.test(trimmed) || /^Why (this works|recovery)/i.test(trimmed)
}

export function isPlainLeadLine(trimmed) {
  return /^(🟢|🟡|🔴)?\s*(PRIMED|CAUTION|REST)\s*\/\s*(ACCUMULATE|ABSORB|RESTORE)/i.test(trimmed)
}

export function isSpineHeader(trimmed) {
  return /SPINE LOCK/i.test(trimmed)
}

export function isCoachSectionHeader(trimmed) {
  return (
    /^(⚡|🔬|🫀|🧠|🧭|📅|🗓️|📊|⚠️|🟢|🟡|🔴|🗣️|💡|🛡️|💬|📌|⚕️)\s/.test(trimmed) ||
    isTodayCallHeader(trimmed) ||
    isLockerHeader(trimmed) ||
    isWhatChangedHeader(trimmed) ||
    isDeepDiveHeader(trimmed) ||
    isSpineHeader(trimmed) ||
    /WEEKLY TRANSLATIONS/i.test(trimmed) ||
    /WHAT LANDED/i.test(trimmed) ||
    isRevisedWeekHeader(trimmed)
  )
}

export function countWhatChangedItems(lines) {
  return (lines || []).filter((line) => {
    const trimmed = String(line || '').trim()
    if (!trimmed || isWhatChangedHeader(trimmed)) return false
    return /^[•\-*]/.test(trimmed) || trimmed.startsWith('**')
  }).length
}

export function whatChangedSummary(count) {
  const n = Number(count) || 0
  if (n <= 0) return 'What changed this week'
  if (n === 1) return '1 thing changed this week'
  return `${n} things changed this week`
}

export function countWeekTableRows(tableRows) {
  if (!tableRows?.length) return 0
  const parsed = tableRows.map(parseTableRow).filter((row) => row.length)
  return parsed.slice(1).filter((row) => !isTableDivider(row)).length
}

export function messageHasScheduleContent(content) {
  const text = String(content || '')
  return (
    isRevisedWeekHeader(text) ||
    /WHAT CHANGED/i.test(text) ||
    /\|\s*Day\s*\|\s*Session\s*\|/i.test(text)
  )
}

export function goDeeperPrompt(content) {
  if (/WHAT CHANGED/i.test(content || '')) {
    return 'Explain why these zone and session changes work — plain language, max 3 bullets.'
  }
  return "Explain why this week's plan works — plain language, one watch number, no lecture."
}

export function parseContentToBlocks(content) {
  const lines = String(content || '').split('\n')
  const blocks = []
  let table = []
  lines.forEach((line) => {
    if (isTableLine(line)) {
      table.push(line)
      return
    }
    if (table.length) {
      blocks.push({ type: 'table', rows: table })
      table = []
    }
    blocks.push({ type: 'line', line })
  })
  if (table.length) {
    blocks.push({ type: 'table', rows: table })
  }
  return blocks
}

export function foldCoachBlocks(blocks) {
  const out = []
  for (let index = 0; index < blocks.length; index += 1) {
    const block = blocks[index]
    if (block.type !== 'line') {
      out.push(block)
      continue
    }
    const trimmed = block.line.trim()

    if (isPlainLeadLine(trimmed)) {
      const lines = [block.line]
      let cursor = index + 1
      while (cursor < blocks.length && blocks[cursor].type === 'line') {
        const next = blocks[cursor].line.trim()
        if (next && isCoachSectionHeader(next)) break
        if (!next) break
        lines.push(blocks[cursor].line)
        cursor += 1
      }
      out.push({ type: 'plainLead', lines, tone: todayCallTone(lines.join('\n')) || 'amber' })
      index = cursor - 1
      continue
    }

    if (isWhatChangedHeader(trimmed)) {
      const lines = [block.line]
      let cursor = index + 1
      while (cursor < blocks.length && blocks[cursor].type === 'line') {
        const next = blocks[cursor].line.trim()
        if (next && isCoachSectionHeader(next) && !isWhatChangedHeader(next)) break
        lines.push(blocks[cursor].line)
        cursor += 1
      }
      out.push({
        type: 'whatChanged',
        lines,
        itemCount: countWhatChangedItems(lines),
        summary: whatChangedSummary(countWhatChangedItems(lines)),
      })
      index = cursor - 1
      continue
    }

    if (isDeepDiveHeader(trimmed)) {
      const lines = [block.line]
      let cursor = index + 1
      while (cursor < blocks.length && blocks[cursor].type === 'line') {
        const next = blocks[cursor].line.trim()
        if (next && isCoachSectionHeader(next) && !isDeepDiveHeader(next)) break
        lines.push(blocks[cursor].line)
        cursor += 1
      }
      out.push({ type: 'deepDive', lines })
      index = cursor - 1
      continue
    }

    if (isTodayCallHeader(trimmed)) {
      const lines = [block.line]
      let cursor = index + 1
      while (cursor < blocks.length && blocks[cursor].type === 'line') {
        const next = blocks[cursor].line.trim()
        if (
          next &&
          isCoachSectionHeader(next) &&
          !isTodayCallHeader(next) &&
          !todayCallTone(next)
        ) {
          break
        }
        lines.push(blocks[cursor].line)
        cursor += 1
      }
      out.push({
        type: 'todayCall',
        lines,
        tone: todayCallTone(lines.join('\n')) || 'amber',
      })
      index = cursor - 1
      continue
    }

    if (isLockerHeader(trimmed)) {
      const lines = [block.line]
      let cursor = index + 1
      while (cursor < blocks.length && blocks[cursor].type === 'line') {
        const next = blocks[cursor].line.trim()
        if (!next) {
          cursor += 1
          continue
        }
        if (isCoachSectionHeader(next) && !isLockerHeader(next)) break
        lines.push(blocks[cursor].line)
        cursor += 1
        break
      }
      out.push({ type: 'locker', lines })
      index = cursor - 1
      continue
    }

    if (isSpineHeader(trimmed)) {
      const lines = [block.line]
      let cursor = index + 1
      while (cursor < blocks.length && blocks[cursor].type === 'line') {
        const next = blocks[cursor].line.trim()
        if (next && isCoachSectionHeader(next) && !isSpineHeader(next)) break
        lines.push(blocks[cursor].line)
        cursor += 1
      }
      out.push({ type: 'spine', lines })
      index = cursor - 1
      continue
    }

    out.push(block)
  }
  return out
}

export function foldCoachContent(content) {
  return foldCoachBlocks(parseContentToBlocks(content))
}

export function extractDeepDiveBlocks(folded) {
  return folded.filter((block) => block.type === 'deepDive')
}

export function hasGoDeeperContent(folded, content) {
  if (extractDeepDiveBlocks(folded).length > 0) return true
  if (messageHasScheduleContent(content)) return true
  return (folded || []).some(
    (block) =>
      block.type === 'whatChanged' ||
      block.type === 'table' ||
      (block.type === 'line' && isRevisedWeekHeader(String(block.line || '').trim())),
  )
}
