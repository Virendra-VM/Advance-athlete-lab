import { useEffect, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { Pin, Send, Sparkles, X, CalendarPlus } from 'lucide-react'
import { parseUtcDate } from '../../utils/formatters'
import WeekPlan from './WeekPlan'
import {
  loadPins,
  pinFromMessage,
  pinFromWeek,
  removePin,
  savePins,
  upsertPin,
} from './chatPins'

const PROMPTS = [
  "How was today's session?",
  'How should I adjust this week?',
  'How easy should my easy sessions feel?',
  'I missed two sessions — what now?',
]

const THINK_STATUS = [
  'Reading your training…',
  'Checking sleep and load…',
  'Writing the brief…',
]

function prefersReducedMotion() {
  try {
    return Boolean(window.matchMedia?.('(prefers-reduced-motion: reduce)')?.matches)
  } catch {
    return false
  }
}

function tokenize(text) {
  return String(text || '').split(/(\s+)/).filter(Boolean)
}

function ThinkingIndicator() {
  const [index, setIndex] = useState(0)
  const reduceMotion = prefersReducedMotion()

  useEffect(() => {
    const timer = window.setInterval(
      () => setIndex((current) => (current + 1) % THINK_STATUS.length),
      1500,
    )
    return () => window.clearInterval(timer)
  }, [])

  return (
    <div
      className="mx-auto w-full max-w-3xl px-1"
      role="status"
      aria-live="polite"
      aria-label="Coach is thinking"
    >
      <div className="flex items-center gap-3">
        <span className="coach-think-orb" aria-hidden="true">
          <Sparkles className="relative z-10 h-3.5 w-3.5" />
        </span>
        <span className="coach-think" aria-hidden="true">
          <span />
          <span />
          <span />
        </span>
        <div className="relative h-5 min-w-0 flex-1 overflow-hidden">
          <AnimatePresence mode="wait" initial={false}>
            <motion.p
              key={THINK_STATUS[index]}
              initial={reduceMotion ? false : { opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={reduceMotion ? { opacity: 1, y: 0 } : { opacity: 0, y: -6 }}
              transition={{ duration: 0.22, ease: 'easeOut' }}
              className="coach-think-label absolute inset-0 text-sm font-medium"
            >
              {THINK_STATUS[index]}
            </motion.p>
          </AnimatePresence>
        </div>
      </div>
      <div className="mt-3 max-w-md space-y-2 pl-11" aria-hidden="true">
        <div className="coach-think-bar w-[92%]" />
        <div className="coach-think-bar w-[74%]" />
        <div className="coach-think-bar w-[58%]" />
      </div>
    </div>
  )
}

function renderInline(text) {
  const parts = String(text).split(/(\*\*[^*]+\*\*)/g)
  return parts.map((part, index) => {
    if (part.startsWith('**') && part.endsWith('**') && part.length > 4) {
      return (
        <strong key={index} className="font-semibold">
          {part.slice(2, -2)}
        </strong>
      )
    }
    return part
  })
}

function parseTableRow(line) {
  return line
    .trim()
    .replace(/^\|/, '')
    .replace(/\|$/, '')
    .split('|')
    .map((cell) => cell.trim())
}

function isTableDivider(cells) {
  return cells.length > 0 && cells.every((cell) => /^:?-{2,}:?$/.test(cell.replace(/\s/g, '')) || cell === '')
}

function isTableLine(line) {
  const trimmed = line.trim()
  return trimmed.startsWith('|') && trimmed.endsWith('|') && trimmed.length > 2
}

function isRevisedWeekHeader(trimmed) {
  return /REVISED WEEK/i.test(trimmed) || /^🗓️\s/.test(trimmed)
}

function todayCallTone(text) {
  if (/PRIMED\s*\/\s*ACCUMULATE/i.test(text)) return 'green'
  if (/CAUTION\s*\/\s*ABSORB/i.test(text)) return 'amber'
  if (/REST\s*\/\s*RESTORE/i.test(text)) return 'red'
  return null
}

function isTodayCallHeader(trimmed) {
  return /TODAY'S CALL/i.test(trimmed)
}

function isLockerHeader(trimmed) {
  return /LOCKER ROOM DIRECTIVE/i.test(trimmed)
}

function isSpineHeader(trimmed) {
  return /SPINE LOCK/i.test(trimmed)
}

function isCoachSectionHeader(trimmed) {
  return (
    /^(⚡|🔬|🫀|🧠|📅|🗓️|⚠️|🟢|🟡|🔴|🗣️|💡|🛡️)\s/.test(trimmed) ||
    isTodayCallHeader(trimmed) ||
    isLockerHeader(trimmed) ||
    isSpineHeader(trimmed) ||
    /WEEKLY TRANSLATIONS/i.test(trimmed) ||
    isRevisedWeekHeader(trimmed)
  )
}

function foldCoachBlocks(blocks) {
  const out = []
  for (let index = 0; index < blocks.length; index += 1) {
    const block = blocks[index]
    if (block.type !== 'line') {
      out.push(block)
      continue
    }
    const trimmed = block.line.trim()
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

function renderLineStack(lines, caret) {
  return lines.map((line, lineIndex) => {
    const last = lineIndex === lines.length - 1
    if (!line.trim()) {
      return (
        <div key={lineIndex} className="h-2">
          {last && caret ? <span className="coach-stream-caret" aria-hidden="true" /> : null}
        </div>
      )
    }
    return (
      <p key={lineIndex} className="text-[var(--aal-ink)]">
        {renderInline(line)}
        {last && caret ? <span className="coach-stream-caret" aria-hidden="true" /> : null}
      </p>
    )
  })
}

function ApplyWeekButton({ onApply, applying, weekOnSchedule }) {
  return (
    <button
      type="button"
      onClick={onApply}
      disabled={applying}
      className="inline-flex shrink-0 items-center justify-center gap-2 rounded-xl bg-sage px-3.5 py-2 text-sm font-semibold text-white shadow-sm transition hover:brightness-105 disabled:opacity-60"
    >
      <CalendarPlus className={`h-4 w-4 ${applying ? 'sync-spin' : ''}`} />
      {applying
        ? 'Saving to Schedule…'
        : weekOnSchedule
          ? 'Replace week on Schedule'
          : 'Add week to Schedule'}
    </button>
  )
}

function CoachReplyBody({
  content,
  mine,
  caret = false,
  applyWeek = null,
}) {
  if (mine) {
    return <p className="whitespace-pre-wrap leading-relaxed">{content}</p>
  }
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

  const folded = foldCoachBlocks(blocks)
  let placedApply = false
  const lastFolded = folded.length - 1

  return (
    <div className="space-y-0.5 text-[15px] leading-7">
      {folded.map((block, blockIndex) => {
        const last = blockIndex === lastFolded
        if (block.type === 'todayCall') {
          return (
            <div
              key={blockIndex}
              className={`coach-today-call coach-today-call-${block.tone} my-3`}
            >
              {renderLineStack(block.lines, last && caret)}
            </div>
          )
        }
        if (block.type === 'locker') {
          return (
            <div key={blockIndex} className="coach-locker-directive my-3">
              {renderLineStack(block.lines, last && caret)}
            </div>
          )
        }
        if (block.type === 'spine') {
          return (
            <div key={blockIndex} className="coach-spine-lock my-3">
              {renderLineStack(block.lines, last && caret)}
            </div>
          )
        }
        if (block.type === 'table') {
          const parsed = block.rows.map(parseTableRow).filter((row) => row.length)
          const header = parsed[0] || []
          const body = parsed.slice(1).filter((row) => !isTableDivider(row))
          const tableEl = (
            <div className="coach-md-table-wrap overflow-x-auto">
              <table className="coach-md-table">
                <thead>
                  <tr>
                    {header.map((cell, cellIndex) => (
                      <th key={cellIndex}>{renderInline(cell)}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {body.map((row, rowIndex) => (
                    <tr key={rowIndex}>
                      {row.map((cell, cellIndex) => (
                        <td key={cellIndex}>{renderInline(cell)}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )
          if (applyWeek && !placedApply) {
            placedApply = true
            return (
              <div key={blockIndex} className="my-3 space-y-2">
                <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                  {applyWeek}
                </div>
                {tableEl}
              </div>
            )
          }
          return (
            <div key={blockIndex} className="my-3">
              {tableEl}
            </div>
          )
        }
        const line = block.line
        const trimmed = line.trim()
        if (!trimmed) {
          return (
            <div key={blockIndex} className="h-2.5">
              {last && caret ? <span className="coach-stream-caret" aria-hidden="true" /> : null}
            </div>
          )
        }
        const isHeader = isCoachSectionHeader(trimmed)
        if (isRevisedWeekHeader(trimmed) && applyWeek) {
          placedApply = true
          return (
            <div
              key={blockIndex}
              className="mt-4 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between"
            >
              <p className="font-semibold tracking-tight text-[var(--aal-ink)]">
                {renderInline(line)}
                {last && caret ? <span className="coach-stream-caret" aria-hidden="true" /> : null}
              </p>
              {applyWeek}
            </div>
          )
        }
        return (
          <p
            key={blockIndex}
            className={
              isHeader
                ? 'mt-4 first:mt-0 font-semibold tracking-tight text-[var(--aal-ink)]'
                : 'text-[var(--aal-ink)]/90'
            }
          >
            {renderInline(line)}
            {last && caret ? <span className="coach-stream-caret" aria-hidden="true" /> : null}
          </p>
        )
      })}
    </div>
  )
}

function timeLabel(value) {
  const parsed = parseUtcDate(value)
  if (!parsed) return ''
  return parsed.toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' })
}

function isNearBottom(node, threshold = 96) {
  if (!node) return true
  return node.scrollHeight - node.scrollTop - node.clientHeight < threshold
}

function pinWho(pin) {
  if (pin.type === 'week') return 'This week'
  return pin.role === 'user' ? 'You' : 'Coach'
}

function pinSnippet(pin) {
  if (pin.type === 'week') return pin.summary || pin.title || 'This week'
  return String(pin.content || '').replace(/\s+/g, ' ').trim()
}

function PinnedBar({ pin, onJump, onUnpin }) {
  return (
    <div className="flex items-stretch border-b border-[var(--aal-line)] bg-[var(--aal-card)]/90">
      <div className="w-[3px] shrink-0 bg-sage" />
      <button
        type="button"
        onClick={onJump}
        className="mx-auto flex min-w-0 w-full max-w-3xl items-center gap-3 px-4 py-2 text-left transition hover:bg-sage/5"
      >
        <Pin className="h-3.5 w-3.5 shrink-0 fill-current text-sage" />
        <div className="min-w-0 flex-1">
          <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-sage">
            Pinned message
          </p>
          <p className="truncate text-[13px] leading-5 text-[var(--aal-ink)]">
            <span className="text-[var(--aal-muted)]">{pinWho(pin)} · </span>
            {pinSnippet(pin)}
          </p>
        </div>
      </button>
      <button
        type="button"
        onClick={onUnpin}
        className="px-3 text-[var(--aal-muted)] transition hover:text-[var(--aal-ink)]"
        aria-label="Unpin"
      >
        <X className="h-4 w-4" />
      </button>
    </div>
  )
}

function looksLikeWeekTable(content) {
  const text = String(content || '')
  return (
    /REVISED WEEK/i.test(text) ||
    /\|\s*Day\s*\|\s*Date\s*\|/i.test(text) ||
    /\|\s*Day\s*\|\s*Session\s*\|/i.test(text) ||
    /Coach'?s Secret Rule/i.test(text) ||
    /Primary Focus/i.test(text) ||
    (/\bMonday\b/i.test(text) && /\bSunday\b/i.test(text) && /\b\d{4}-\d{2}-\d{2}\b/.test(text))
  )
}

function MessageRow({
  message,
  mine,
  pinned,
  onPin,
  streamed,
  streaming,
  onApplyWeek,
  applying,
  weekOnSchedule,
}) {
  const canPin =
    !streaming &&
    (typeof message.id === 'number' ||
      (typeof message.id === 'string' && !String(message.id).startsWith('pending-')))
  const body = streamed != null ? streamed : message.content
  const applyWeek =
    !streaming && onApplyWeek && (message.plan_id || looksLikeWeekTable(body)) ? (
      <ApplyWeekButton
        onApply={() => onApplyWeek(message)}
        applying={applying}
        weekOnSchedule={weekOnSchedule}
      />
    ) : null

  if (mine) {
    return (
      <div id={`coach-msg-${message.id}`} className="group mx-auto flex w-full max-w-3xl justify-end px-1">
        <div className="max-w-[min(85%,36rem)] rounded-3xl rounded-br-lg bg-sage px-4 py-2.5 text-[15px] text-white shadow-sm">
          <CoachReplyBody content={body} mine />
          <div className="mt-1 flex items-center justify-end gap-2 text-[10px] text-white/70">
            <span>{timeLabel(message.created_at)}</span>
            {canPin ? (
              <button
                type="button"
                onClick={onPin}
                className={`inline-flex items-center gap-1 rounded-md px-1 py-0.5 ${
                  pinned ? 'text-white' : 'opacity-80 hover:opacity-100 sm:opacity-0 sm:group-hover:opacity-100'
                }`}
                aria-pressed={pinned}
                aria-label={pinned ? 'Unpin message' : 'Pin message'}
              >
                <Pin className={`h-3 w-3 ${pinned ? 'fill-current' : ''}`} />
                {pinned ? 'Pinned' : 'Pin'}
              </button>
            ) : null}
          </div>
        </div>
      </div>
    )
  }

  return (
    <div id={`coach-msg-${message.id}`} className="group mx-auto w-full max-w-3xl px-1">
      <motion.div
        initial={streaming ? { opacity: 0.55 } : false}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.18 }}
      >
        <CoachReplyBody
          content={body}
          mine={false}
          caret={Boolean(streaming)}
          applyWeek={applyWeek}
        />
      </motion.div>
      {streaming ? null : (
        <div className="mt-2 flex flex-wrap items-center gap-2 text-[10px] text-[var(--aal-muted)]">
          <span>{timeLabel(message.created_at)}</span>
          {canPin ? (
            <button
              type="button"
              onClick={onPin}
              className={`inline-flex items-center gap-1 rounded-md px-1 py-0.5 ${
                pinned ? 'text-sage' : 'opacity-80 hover:opacity-100 sm:opacity-0 sm:group-hover:opacity-100'
              }`}
              aria-pressed={pinned}
              aria-label={pinned ? 'Unpin message' : 'Pin message'}
            >
              <Pin className={`h-3 w-3 ${pinned ? 'fill-current' : ''}`} />
              {pinned ? 'Pinned' : 'Pin'}
            </button>
          ) : null}
        </div>
      )}
    </div>
  )
}

export default function CoachChat({
  messages,
  onSend,
  sending,
  disabled,
  disabledReason,
  plan,
  weekStart,
  generating,
  profileId,
  focalLabel,
  onApplyWeek,
  applyingWeek,
  onAddToSchedule,
}) {
  const [draft, setDraft] = useState('')
  const [pins, setPins] = useState(() => loadPins(profileId))
  const [stream, setStream] = useState(null)
  const listRef = useRef(null)
  const inputRef = useRef(null)
  const stickToBottom = useRef(true)
  const seenIds = useRef(new Set())
  const primed = useRef(false)
  const weekPinId = weekStart ? `week-${weekStart}` : null

  useEffect(() => {
    setPins(loadPins(profileId))
  }, [profileId])

  useEffect(() => {
    savePins(profileId, pins)
  }, [profileId, pins])

  useEffect(() => {
    if (!weekStart) return
    setPins((current) => {
      let changed = false
      const nextWeek = pinFromWeek(plan, weekStart)
      const mapped = current.map((pin) => {
        if (pin.id !== weekPinId) return pin
        if (
          pin.title === nextWeek.title &&
          pin.summary === nextWeek.summary &&
          pin.planId === nextWeek.planId
        ) {
          return pin
        }
        changed = true
        return { ...pin, ...nextWeek, id: weekPinId }
      })
      return changed ? mapped : current
    })
  }, [plan, weekStart, weekPinId])

  useEffect(() => {
    if (!primed.current) {
      messages.forEach((item) => seenIds.current.add(item.id))
      primed.current = true
      return undefined
    }

    const latest = [...messages]
      .reverse()
      .find((item) => item.role !== 'user' && !String(item.id).startsWith('pending-'))
    messages.forEach((item) => {
      if (item.role === 'user' || String(item.id).startsWith('pending-')) {
        seenIds.current.add(item.id)
      }
    })
    if (!latest || seenIds.current.has(latest.id)) return undefined

    seenIds.current.add(latest.id)
    stickToBottom.current = true

    if (prefersReducedMotion() || !latest.content) {
      setStream({ id: latest.id, shown: latest.content || '', done: true })
      return undefined
    }

    const tokens = tokenize(latest.content)
    const duration = Math.min(2000, Math.max(420, Math.round(tokens.length * 5.5)))
    setStream({ id: latest.id, shown: '', done: false })

    let cancelled = false
    let finished = false
    let start = null
    let frame

    const tick = (now) => {
      if (cancelled) return
      if (start == null) start = now
      const progress = Math.min(1, (now - start) / duration)
      const eased = 1 - (1 - progress) ** 3
      const count = Math.max(1, Math.ceil(tokens.length * eased))
      const shown = tokens.slice(0, count).join('')
      if (progress >= 1) {
        finished = true
        setStream({ id: latest.id, shown: latest.content, done: true })
        return
      }
      setStream({ id: latest.id, shown, done: false })
      frame = window.requestAnimationFrame(tick)
    }

    frame = window.requestAnimationFrame(tick)
    return () => {
      cancelled = true
      window.cancelAnimationFrame(frame)
      if (!finished) seenIds.current.delete(latest.id)
    }
  }, [messages])

  useEffect(() => {
    const node = listRef.current
    if (!node || !stickToBottom.current) return
    node.scrollTop = node.scrollHeight
  }, [messages.length, sending, stream?.shown])

  function resizeInput() {
    const node = inputRef.current
    if (!node) return
    node.style.height = 'auto'
    node.style.height = `${Math.min(node.scrollHeight, 160)}px`
  }

  function togglePin(pin) {
    const exists = pins.some((item) => item.id === pin.id)
    setPins((current) => (exists ? removePin(current, pin.id) : upsertPin(current, pin)))
  }

  function jumpToPinned(pin) {
    stickToBottom.current = false
    const target =
      pin.type === 'week'
        ? document.getElementById('coach-week-artifact')
        : document.getElementById(`coach-msg-${pin.messageId}`)
    target?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }

  async function submit(text) {
    const message = (text ?? draft).trim()
    if (!message || sending || disabled) return
    stickToBottom.current = true
    setDraft('')
    requestAnimationFrame(() => {
      if (inputRef.current) {
        inputRef.current.style.height = 'auto'
      }
    })
    await onSend(message)
  }

  const empty = messages.length === 0
  const newestAssistant = [...messages]
    .reverse()
    .find((item) => item.role !== 'user' && !String(item.id).startsWith('pending-'))
  const waitingForStream = Boolean(
    primed.current &&
      newestAssistant &&
      stream?.id !== newestAssistant.id &&
      !seenIds.current.has(newestAssistant.id),
  )
  const emptyStream = Boolean(
    newestAssistant && stream?.id === newestAssistant.id && !stream.done && !stream.shown,
  )
  const holdingReply = waitingForStream || emptyStream
  const activelyStreaming = Boolean(stream && !stream.done && stream.shown)
  const showThinking = Boolean((sending || holdingReply) && !activelyStreaming)

  return (
    <section
      className="coach-chat-canvas flex h-full min-h-0 flex-col overflow-hidden"
      aria-busy={sending || activelyStreaming || holdingReply}
    >
      {pins.length ? (
        <div className="shrink-0">
          {pins.slice(0, 3).map((pin) => (
            <PinnedBar
              key={pin.id}
              pin={pin}
              onJump={() => jumpToPinned(pin)}
              onUnpin={() => togglePin(pin)}
            />
          ))}
        </div>
      ) : null}

      {focalLabel ? (
        <div className="shrink-0 border-b border-[var(--aal-line)] bg-sage/5 px-4 py-2 text-center text-xs text-[var(--aal-muted)]">
          Analysing <span className="font-medium text-[var(--aal-ink)]">{focalLabel}</span>
        </div>
      ) : null}

      <div
        ref={listRef}
        onScroll={(event) => {
          stickToBottom.current = isNearBottom(event.currentTarget)
        }}
        className="min-h-0 flex-1 overflow-y-auto overscroll-contain px-4 py-6 sm:px-6"
      >
        <div className="mx-auto flex min-h-full w-full max-w-3xl flex-col gap-6">
          {weekStart ? (
            <div id="coach-week-artifact">
              <WeekPlan
                plan={plan}
                weekStart={weekStart}
                loading={false}
                generating={generating}
                publishing={applyingWeek}
                onAddToSchedule={onAddToSchedule}
                embedded
                pinned={pins.some((pin) => pin.id === weekPinId)}
                onPin={() => togglePin(pinFromWeek(plan, weekStart))}
              />
            </div>
          ) : null}

          {empty ? (
            <div className="flex flex-1 flex-col items-center justify-center px-4 py-10 text-center">
              <div className="mb-5 flex h-12 w-12 items-center justify-center rounded-2xl bg-sage/15 text-sage">
                <Sparkles className="h-6 w-6" />
              </div>
              <h2 className="font-display text-3xl tracking-tight text-[var(--aal-ink)]">
                What should we look at?
              </h2>
              <p className="mt-2 max-w-md text-sm text-[var(--aal-muted)]">
                Ask about today, remaining days, or how you feel. Your week, wearables, and profile
                are already in context.
              </p>
              <div className="mt-8 flex w-full max-w-xl flex-col gap-2 sm:grid sm:grid-cols-2">
                {PROMPTS.map((prompt) => (
                  <button
                    key={prompt}
                    type="button"
                    disabled={disabled || sending}
                    onClick={() => submit(prompt)}
                    className="rounded-2xl border border-[var(--aal-line)] bg-[var(--aal-card)]/80 px-4 py-3 text-left text-sm text-[var(--aal-ink)]/90 shadow-sm transition hover:border-sage/40 hover:bg-[var(--aal-card)] disabled:opacity-60"
                  >
                    {prompt}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            messages.map((message) => {
              const mine = message.role === 'user'
              if (holdingReply && newestAssistant && message.id === newestAssistant.id) {
                return null
              }
              const pinId = `msg-${message.id}`
              return (
                <MessageRow
                  key={message.id}
                  message={message}
                  mine={mine}
                  pinned={pins.some((pin) => pin.id === pinId)}
                  onPin={() => togglePin(pinFromMessage(message))}
                  streamed={stream?.id === message.id ? stream.shown : null}
                  streaming={stream?.id === message.id && !stream.done}
                  onApplyWeek={mine ? undefined : onApplyWeek}
                  applying={Boolean(applyingWeek)}
                  weekOnSchedule={Boolean(plan?.on_schedule)}
                />
              )
            })
          )}
          <AnimatePresence>
            {showThinking ? (
              <motion.div
                key="coach-thinking"
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -4 }}
                transition={{ duration: 0.2 }}
              >
                <ThinkingIndicator />
              </motion.div>
            ) : null}
          </AnimatePresence>
        </div>
      </div>

      <div className="shrink-0 bg-gradient-to-t from-[var(--aal-bg)] via-[var(--aal-bg)] to-transparent px-3 pb-4 pt-2 sm:px-6">
        <form
          className="mx-auto w-full max-w-3xl"
          onSubmit={(event) => {
            event.preventDefault()
            submit()
          }}
        >
          <div className="flex items-end gap-2 rounded-[1.75rem] border border-[var(--aal-line)] bg-[var(--aal-card)] px-3 py-2 shadow-[0_10px_40px_-18px_rgba(15,23,42,0.45)] focus-within:border-sage/50">
            <textarea
              ref={inputRef}
              rows={1}
              value={draft}
              disabled={disabled}
              onChange={(event) => {
                setDraft(event.target.value)
                resizeInput()
              }}
              onKeyDown={(event) => {
                if (event.key === 'Enter' && !event.shiftKey) {
                  event.preventDefault()
                  submit()
                }
              }}
              placeholder={disabled ? disabledReason : 'Message Coach'}
              className="max-h-40 min-h-11 flex-1 resize-none bg-transparent px-2 py-2.5 text-[15px] leading-6 outline-none"
            />
            <button
              type="submit"
              disabled={disabled || sending || !draft.trim()}
              className="mb-0.5 inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-sage text-white transition hover:brightness-105 disabled:opacity-40"
              aria-label="Send"
            >
              <Send className="h-4 w-4" />
            </button>
          </div>
          <p className="mt-2 text-center text-[10px] text-[var(--aal-muted)]">
            Coaching only — not medical advice.
          </p>
        </form>
      </div>
    </section>
  )
}
