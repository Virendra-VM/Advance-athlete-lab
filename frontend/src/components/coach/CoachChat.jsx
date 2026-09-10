import { Fragment, useEffect, useMemo, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import {
  Pin,
  Send,
  Sparkles,
  Square,
  X,
  CalendarPlus,
  ChevronDown,
  ChevronUp,
  Lightbulb,
} from 'lucide-react'
import { loadComposerDraft, saveComposerDraft } from '../../utils/coachComposerStorage'
import {
  extractDeepDiveBlocks,
  foldCoachContent,
  goDeeperPrompt,
  hasGoDeeperContent,
  isCoachSectionHeader,
  isRevisedWeekHeader,
  isTableDivider,
  parseTableRow,
  countWeekTableRows,
} from '../../utils/coachChatLayout'
import { parseUtcDate } from '../../utils/formatters'
import WeekPlan from './WeekPlan'
import { loadPins, pinFromMessage, removePin, savePins, upsertPin } from './chatPins'

/** Centered reading column — same pattern as ChatGPT / Claude / Gemini (~768px). */
const CHAT_COLUMN = 'mx-auto w-full max-w-3xl'

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
      className={`${CHAT_COLUMN} px-1`}
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

function WhatChangedCard({ block, caret }) {
  const [open, setOpen] = useState(false)
  const bodyLines = block.lines.slice(1)
  return (
    <div className="coach-what-changed my-3 overflow-hidden rounded-xl border border-indigo-200/50 bg-indigo-50/40 dark:border-indigo-500/25 dark:bg-indigo-950/20">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        className="flex w-full items-center justify-between gap-3 px-3 py-2.5 text-left transition hover:bg-indigo-100/40 dark:hover:bg-indigo-900/20"
      >
        <span className="text-sm font-semibold text-[var(--aal-ink)]">
          📊 {block.summary || 'What changed this week'}
        </span>
        {open ? (
          <ChevronUp className="h-4 w-4 shrink-0 text-indigo-500" />
        ) : (
          <ChevronDown className="h-4 w-4 shrink-0 text-indigo-500" />
        )}
      </button>
      {open ? (
        <div className="border-t border-indigo-200/40 px-3 py-2 dark:border-indigo-500/20">
          {renderLineStack(bodyLines, caret)}
        </div>
      ) : null}
    </div>
  )
}

function CollapsibleWeekTable({ tableEl, applyWeek, defaultOpen, rowCount }) {
  const [open, setOpen] = useState(defaultOpen)
  const label = open
    ? 'Hide week plan'
    : rowCount > 0
      ? `Show week plan (${rowCount} days)`
      : 'Show week plan'
  return (
    <div className="my-3 space-y-2">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        {applyWeek}
        <button
          type="button"
          onClick={() => setOpen((value) => !value)}
          aria-expanded={open}
          className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--aal-line)] px-3 py-1.5 text-xs font-semibold text-[var(--aal-ink)] transition hover:bg-[var(--aal-card)]"
        >
          {open ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
          {label}
        </button>
      </div>
      {open ? tableEl : null}
    </div>
  )
}

function GoDeeperSection({ deepDiveBlocks, onAskCoach, disabled }) {
  const [open, setOpen] = useState(false)
  const hasInline = deepDiveBlocks.length > 0
  if (!hasInline && !onAskCoach) return null
  return (
    <div className="coach-go-deeper my-3">
      {!open ? (
        <button
          type="button"
          disabled={disabled}
          onClick={() => {
            if (hasInline) {
              setOpen(true)
              return
            }
            onAskCoach?.()
          }}
          className="inline-flex items-center gap-2 rounded-full border border-[var(--aal-line)] bg-[var(--aal-card)] px-3 py-1.5 text-xs font-semibold text-indigo-600 transition hover:border-indigo-300 hover:bg-indigo-50/50 disabled:opacity-50 dark:text-indigo-300 dark:hover:bg-indigo-950/30"
        >
          <Lightbulb className="h-3.5 w-3.5" />
          Go deeper — why this week?
        </button>
      ) : (
        <div className="rounded-xl border border-[var(--aal-line)] bg-[var(--aal-card)]/80 px-3 py-2">
          <div className="mb-2 flex items-center justify-between gap-2">
            <span className="text-xs font-semibold uppercase tracking-wide text-indigo-500 dark:text-indigo-300">
              Why this works
            </span>
            <button
              type="button"
              onClick={() => setOpen(false)}
              className="text-[10px] font-medium text-[var(--aal-muted)] hover:text-[var(--aal-ink)]"
            >
              Hide
            </button>
          </div>
          {deepDiveBlocks.map((block, index) => (
            <div key={index}>{renderLineStack(block.lines, false)}</div>
          ))}
          {onAskCoach ? (
            <button
              type="button"
              disabled={disabled}
              onClick={onAskCoach}
              className="mt-2 text-xs font-medium text-indigo-600 hover:underline disabled:opacity-50 dark:text-indigo-300"
            >
              Ask the coach for more detail
            </button>
          ) : null}
        </div>
      )}
    </div>
  )
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
      className="inline-flex shrink-0 items-center justify-center gap-2 rounded-xl bg-indigo-600 px-3.5 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-indigo-500 disabled:opacity-60"
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
  weekTableDefaultOpen = true,
  onGoDeeper,
  goDeeperDisabled = false,
}) {
  if (mine) {
    return <p className="whitespace-pre-wrap leading-relaxed">{content}</p>
  }

  const folded = foldCoachContent(content)
  const deepDiveBlocks = extractDeepDiveBlocks(folded)
  const visibleBlocks = folded.filter((block) => block.type !== 'deepDive')
  const showGoDeeper = hasGoDeeperContent(folded, content)
  let placedApply = false
  const lastVisible = visibleBlocks.length - 1

  const handleAskCoach = onGoDeeper
    ? () => onGoDeeper(goDeeperPrompt(content))
    : undefined

  return (
    <div className="space-y-0.5 text-[15px] leading-7">
      {visibleBlocks.map((block, blockIndex) => {
        const last = blockIndex === lastVisible && !showGoDeeper
        if (block.type === 'plainLead') {
          return (
            <div
              key={blockIndex}
              className={`coach-plain-lead coach-today-call-${block.tone} my-3 rounded-lg border border-white/10 bg-white/5 px-3 py-2`}
            >
              {renderLineStack(block.lines, last && caret)}
            </div>
          )
        }
        if (block.type === 'whatChanged') {
          return (
            <WhatChangedCard key={blockIndex} block={block} caret={last && caret} />
          )
        }
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
          const rowCount = countWeekTableRows(block.rows)
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
              <CollapsibleWeekTable
                key={blockIndex}
                tableEl={tableEl}
                applyWeek={applyWeek}
                defaultOpen={weekTableDefaultOpen}
                rowCount={rowCount}
              />
            )
          }
          return (
            <CollapsibleWeekTable
              key={blockIndex}
              tableEl={tableEl}
              applyWeek={null}
              defaultOpen={weekTableDefaultOpen}
              rowCount={rowCount}
            />
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
      {showGoDeeper && !caret ? (
        <GoDeeperSection
          deepDiveBlocks={deepDiveBlocks}
          onAskCoach={handleAskCoach}
          disabled={goDeeperDisabled}
        />
      ) : null}
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
      <div className="w-[3px] shrink-0 bg-indigo-500" />
      <button
        type="button"
        onClick={onJump}
        className={`${CHAT_COLUMN} flex min-w-0 items-center gap-3 px-4 py-2 text-left transition hover:bg-indigo-50/60 dark:hover:bg-indigo-950/20`}
      >
        <Pin className="h-3.5 w-3.5 shrink-0 fill-current text-indigo-500 dark:text-indigo-300" />
        <div className="min-w-0 flex-1">
          <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-indigo-500 dark:text-indigo-300">
            {pin.type === 'week' ? 'Pinned week' : 'Pinned message'}
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

function findWeekAnchorMessageId(messages, plan) {
  const workouts = plan?.plan?.workouts
  if (!plan?.plan_id || !Array.isArray(workouts) || !workouts.length) return null

  for (let i = messages.length - 1; i >= 0; i--) {
    const message = messages[i]
    if (message.role === 'user') continue
    if (message.plan_id === plan.plan_id) return message.id
  }

  for (let i = messages.length - 1; i >= 0; i--) {
    const message = messages[i]
    if (message.role !== 'user' && looksLikeWeekTable(message.content)) return message.id
  }

  return null
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
  isLatestAssistant,
  onGoDeeper,
  goDeeperDisabled,
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
      <div id={`coach-msg-${message.id}`} className={`group ${CHAT_COLUMN} flex justify-end px-1`}>
        <div className="max-w-[min(85%,36rem)] rounded-2xl rounded-br-md border border-indigo-300/40 bg-indigo-50/80 px-4 py-3 text-[15px] text-[var(--aal-ink)] shadow-sm dark:border-indigo-500/30 dark:bg-indigo-950/30">
          <CoachReplyBody content={body} mine />
          <div className="mt-1 flex items-center justify-end gap-2 text-[10px] text-[var(--aal-muted)]">
            <span>{timeLabel(message.created_at)}</span>
            {canPin ? (
              <button
                type="button"
                onClick={onPin}
                className={`inline-flex items-center gap-1 rounded-md px-1 py-0.5 ${
                  pinned
                    ? 'text-indigo-600 dark:text-indigo-300'
                    : 'opacity-80 hover:opacity-100 sm:opacity-0 sm:group-hover:opacity-100'
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
    <div id={`coach-msg-${message.id}`} className={`group ${CHAT_COLUMN} px-1`}>
      <motion.div
        initial={streaming ? { opacity: 0.55 } : false}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.18 }}
        className="rounded-2xl border border-[var(--aal-line)] bg-[var(--aal-card)] px-4 py-3 shadow-sm"
      >
        <CoachReplyBody
          content={body}
          mine={false}
          caret={Boolean(streaming)}
          applyWeek={applyWeek}
          weekTableDefaultOpen={Boolean(isLatestAssistant)}
          onGoDeeper={onGoDeeper}
          goDeeperDisabled={goDeeperDisabled}
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
                pinned
                  ? 'text-indigo-500 dark:text-indigo-300'
                  : 'opacity-80 hover:opacity-100 sm:opacity-0 sm:group-hover:opacity-100'
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
  onStop = () => {},
  sending,
  disabled,
  disabledReason,
  plan,
  weekStart,
  profileId,
  focalLabel,
  onApplyWeek,
  applyingWeek,
  onAddToSchedule,
  initialDraft = '',
  draftSeed = null,
  composerHint = '',
  proactivePrompts = [],
  onDismissProactive,
  externalStream = null,
}) {
  const [draft, setDraft] = useState('')
  const [pins, setPins] = useState(() => loadPins(profileId))
  const skipDraftPersist = useRef(false)
  const [stream, setStream] = useState(null)
  const listRef = useRef(null)
  const inputRef = useRef(null)
  const stickToBottom = useRef(true)
  const seenIds = useRef(new Set())
  const primed = useRef(false)
  const hadExternalStream = useRef(false)
  const hasWeek = Boolean((plan?.plan?.workouts || []).length)
  const weekAnchorMessageId = useMemo(
    () => findWeekAnchorMessageId(messages, plan),
    [messages, plan],
  )

  useEffect(() => {
    setPins(loadPins(profileId))
  }, [profileId])

  useEffect(() => {
    if (!profileId) return
    skipDraftPersist.current = true
    setDraft(loadComposerDraft(profileId))
    requestAnimationFrame(() => {
      resizeInput()
      skipDraftPersist.current = false
    })
  }, [profileId])

  useEffect(() => {
    if (!profileId || skipDraftPersist.current) return
    saveComposerDraft(profileId, draft)
  }, [profileId, draft])

  useEffect(() => {
    if (!draftSeed || !initialDraft) return
    skipDraftPersist.current = true
    setDraft(initialDraft)
    saveComposerDraft(profileId, initialDraft)
    requestAnimationFrame(() => {
      resizeInput()
      const node = inputRef.current
      if (!node) return
      node.focus()
      const len = initialDraft.length
      node.setSelectionRange(len, len)
      skipDraftPersist.current = false
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [draftSeed, initialDraft])

  useEffect(() => {
    savePins(profileId, pins)
  }, [profileId, pins])

  useEffect(() => {
    if (externalStream) {
      hadExternalStream.current = true
      return undefined
    }
    if (hadExternalStream.current) {
      hadExternalStream.current = false
      const latest = [...messages]
        .reverse()
        .find((item) => item.role !== 'user' && !String(item.id).startsWith('pending-'))
      if (latest) {
        seenIds.current.add(latest.id)
        setStream({ id: latest.id, shown: latest.content || '', done: true })
      }
      return undefined
    }

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
  }, [messages.length, sending, stream?.shown, weekAnchorMessageId, externalStream])

  const activeStream = externalStream ?? stream

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
      pin.type === 'week' && weekAnchorMessageId
        ? document.getElementById(`coach-week-artifact-${weekAnchorMessageId}`)
        : document.getElementById(`coach-msg-${pin.messageId}`)
    target?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }

  async function submit(text, options = {}) {
    const message = (text ?? draft).trim()
    if (!message || sending || disabled) return
    stickToBottom.current = true
    skipDraftPersist.current = true
    setDraft('')
    saveComposerDraft(profileId, '')
    requestAnimationFrame(() => {
      if (inputRef.current) {
        inputRef.current.style.height = 'auto'
      }
    })
    await onSend(message, {
      activityId: options.activityId,
      restoreOnCancel: (restoreText) => {
        skipDraftPersist.current = true
        setDraft(restoreText)
        saveComposerDraft(profileId, restoreText)
        requestAnimationFrame(() => {
          resizeInput()
          const node = inputRef.current
          if (!node) return
          node.focus()
          const len = restoreText.length
          node.setSelectionRange(len, len)
          skipDraftPersist.current = false
        })
      },
    })
    skipDraftPersist.current = false
  }

  const empty = messages.length === 0
  const newestAssistant = [...messages]
    .reverse()
    .find((item) => item.role !== 'user' && !String(item.id).startsWith('pending-'))
  const waitingForStream = Boolean(
    !externalStream &&
      primed.current &&
      newestAssistant &&
      activeStream?.id !== newestAssistant.id &&
      !seenIds.current.has(newestAssistant.id),
  )
  const emptyStream = Boolean(
    newestAssistant &&
      activeStream?.id === newestAssistant.id &&
      !activeStream.done &&
      !activeStream.shown,
  )
  const holdingReply = waitingForStream || emptyStream
  const activelyStreaming = Boolean(activeStream && !activeStream.done && activeStream.shown)
  const showThinking = Boolean((sending || holdingReply) && !activelyStreaming)

  return (
    <section
      className="flex h-full min-h-0 flex-col overflow-hidden bg-[var(--aal-bg)]"
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
        <div className="shrink-0 border-b border-[var(--aal-line)] bg-indigo-50/50 px-4 py-2 text-center text-xs text-[var(--aal-muted)] dark:bg-indigo-950/20">
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
        <div className={`${CHAT_COLUMN} flex min-h-full flex-col gap-6`}>
          {empty ? (
            <div className="relative overflow-hidden rounded-2xl border border-[var(--aal-line)] px-4 py-10 text-center sm:px-8">
              <div
                className="pointer-events-none absolute inset-0"
                style={{
                  background:
                    'radial-gradient(120% 80% at 0% 0%, rgba(55,48,163,0.12), transparent 55%), radial-gradient(90% 70% at 100% 20%, rgba(56,189,248,0.08), transparent 50%), linear-gradient(165deg, var(--aal-card), color-mix(in srgb, #312e81 5%, var(--aal-card)))',
                }}
              />
              <div className="relative flex flex-col items-center">
                <div className="mb-5 flex h-12 w-12 items-center justify-center rounded-xl bg-indigo-600/15 text-indigo-600 dark:text-indigo-300">
                  <Sparkles className="h-6 w-6" />
                </div>
                <h2 className="font-display text-3xl tracking-tight text-[var(--aal-ink)]">
                  What should we look at?
                </h2>
                <p className="mt-2 max-w-md text-sm text-[var(--aal-muted)]">
                  Ask about today, remaining days, or how you feel. Your week, wearables, and profile
                  are already in context.
                </p>
                {proactivePrompts.length > 0 ? (
                  <div className="mt-6 flex w-full max-w-xl flex-col gap-2">
                    <p className="text-xs font-semibold uppercase tracking-wide text-indigo-500 dark:text-indigo-300">
                      New activity synced
                    </p>
                    {proactivePrompts.map((prompt) => (
                      <div
                        key={prompt.id}
                        className="flex items-stretch gap-2 rounded-xl border border-indigo-200/60 bg-indigo-50/40 dark:border-indigo-500/30 dark:bg-indigo-950/20"
                      >
                        <button
                          type="button"
                          disabled={disabled || sending}
                          onClick={() =>
                            submit(prompt.message, {
                              activityId: prompt.activity_id,
                            })
                          }
                          className="flex flex-1 items-center gap-2 px-4 py-3 text-left text-sm text-[var(--aal-ink)] transition hover:bg-indigo-100/50 disabled:opacity-60 dark:hover:bg-indigo-900/30"
                        >
                          <Sparkles className="h-4 w-4 shrink-0 text-indigo-500" />
                          <span>{prompt.summary}</span>
                        </button>
                        {onDismissProactive ? (
                          <button
                            type="button"
                            aria-label="Dismiss suggestion"
                            onClick={() => onDismissProactive(prompt.id)}
                            className="px-3 text-[var(--aal-muted)] transition hover:text-[var(--aal-ink)]"
                          >
                            <X className="h-4 w-4" />
                          </button>
                        ) : null}
                      </div>
                    ))}
                  </div>
                ) : null}
                <div className="mt-8 flex w-full max-w-xl flex-col gap-2 sm:grid sm:grid-cols-2">
                  {PROMPTS.map((prompt) => (
                    <button
                      key={prompt}
                      type="button"
                      disabled={disabled || sending}
                      onClick={() => submit(prompt)}
                      className="rounded-xl border border-[var(--aal-line)] bg-[var(--aal-card)]/90 px-4 py-3 text-left text-sm text-[var(--aal-ink)]/90 shadow-sm transition hover:border-indigo-300 hover:bg-[var(--aal-card)] disabled:opacity-60 dark:hover:border-indigo-500/40"
                    >
                      {prompt}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          ) : (
            messages.map((message) => {
              const mine = message.role === 'user'
              if (holdingReply && newestAssistant && message.id === newestAssistant.id) {
                return null
              }
              const pinId = `msg-${message.id}`
              const showWeekAfter =
                weekAnchorMessageId === message.id && hasWeek && weekStart
              return (
                <Fragment key={message.id}>
                  <MessageRow
                    message={message}
                    mine={mine}
                    pinned={pins.some((pin) => pin.id === pinId)}
                    onPin={() => togglePin(pinFromMessage(message))}
                    streamed={activeStream?.id === message.id ? activeStream.shown : null}
                    streaming={activeStream?.id === message.id && !activeStream.done}
                    onApplyWeek={mine ? undefined : onApplyWeek}
                    applying={Boolean(applyingWeek)}
                    weekOnSchedule={Boolean(plan?.on_schedule)}
                    isLatestAssistant={
                      !mine &&
                      newestAssistant != null &&
                      message.id === newestAssistant.id
                    }
                    onGoDeeper={mine ? undefined : submit}
                    goDeeperDisabled={disabled || sending}
                  />
                  {showWeekAfter ? (
                    <div id={`coach-week-artifact-${message.id}`}>
                      <WeekPlan
                        plan={plan}
                        weekStart={weekStart}
                        loading={false}
                        publishing={applyingWeek}
                        onAddToSchedule={onAddToSchedule}
                        embedded
                      />
                    </div>
                  ) : null}
                </Fragment>
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
                className="rounded-2xl border border-[var(--aal-line)] bg-[var(--aal-card)] px-4 py-3 shadow-sm"
              >
                <ThinkingIndicator />
              </motion.div>
            ) : null}
          </AnimatePresence>
        </div>
      </div>

      <div className="shrink-0 bg-gradient-to-t from-[var(--aal-bg)] via-[var(--aal-bg)] to-transparent px-3 pb-4 pt-2 sm:px-6">
        <form
          className={CHAT_COLUMN}
          onSubmit={(event) => {
            event.preventDefault()
            submit()
          }}
        >
          {composerHint ? (
            <p className="mb-2 text-center text-xs text-[var(--aal-muted)]">{composerHint}</p>
          ) : null}
          {!empty && proactivePrompts.length > 0 ? (
            <div className="mb-3 flex flex-col gap-2">
              {proactivePrompts.map((prompt) => (
                <div
                  key={prompt.id}
                  className="flex items-stretch gap-2 rounded-xl border border-indigo-200/50 bg-indigo-50/40 dark:border-indigo-500/25 dark:bg-indigo-950/20"
                >
                  <button
                    type="button"
                    disabled={disabled || sending}
                    onClick={() =>
                      submit(prompt.message, { activityId: prompt.activity_id })
                    }
                    className="flex flex-1 items-center gap-2 px-3 py-2 text-left text-sm text-[var(--aal-ink)] transition hover:bg-indigo-100/40 disabled:opacity-60 dark:hover:bg-indigo-900/25"
                  >
                    <Sparkles className="h-3.5 w-3.5 shrink-0 text-indigo-500" />
                    <span>{prompt.summary}</span>
                  </button>
                  {onDismissProactive ? (
                    <button
                      type="button"
                      aria-label="Dismiss suggestion"
                      onClick={() => onDismissProactive(prompt.id)}
                      className="px-2 text-[var(--aal-muted)] transition hover:text-[var(--aal-ink)]"
                    >
                      <X className="h-3.5 w-3.5" />
                    </button>
                  ) : null}
                </div>
              ))}
            </div>
          ) : null}
          <div className="flex items-end gap-2 rounded-2xl border border-indigo-300/40 bg-indigo-50/50 px-3 py-2 shadow-sm transition focus-within:border-indigo-300/60 focus-within:bg-indigo-50/80 dark:border-indigo-500/30 dark:bg-indigo-950/25 dark:focus-within:border-indigo-500/50 dark:focus-within:bg-indigo-950/35">
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
              className="max-h-40 min-h-11 flex-1 resize-none bg-transparent px-2 py-2.5 text-[15px] leading-6 text-[var(--aal-ink)] outline-none placeholder:text-[var(--aal-muted)]"
            />
            {sending ? (
              <button
                type="button"
                onClick={onStop}
                className="mb-0.5 inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-[var(--aal-ink)] text-[var(--aal-bg)] transition hover:brightness-110"
                aria-label="Stop"
              >
                <Square className="h-3.5 w-3.5 fill-current" />
              </button>
            ) : (
              <button
                type="submit"
                disabled={disabled || !draft.trim()}
                className="mb-0.5 inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-indigo-600 text-white transition hover:bg-indigo-500 disabled:opacity-40"
                aria-label="Send"
              >
                <Send className="h-4 w-4" />
              </button>
            )}
          </div>
          <p className="mt-2 text-center text-[10px] text-[var(--aal-muted)]">
            Coaching only — not medical advice.
          </p>
        </form>
      </div>
    </section>
  )
}
