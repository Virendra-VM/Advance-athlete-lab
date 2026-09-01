import { useEffect, useRef, useState } from 'react'
import { Pin, Send, X } from 'lucide-react'
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
  'How should I adjust this week?',
  'How easy should my easy sessions feel?',
  'I missed two sessions — what now?',
]

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
    <div className="flex items-stretch border-b border-[var(--aal-line)] bg-[var(--aal-card)]">
      <div className="w-[3px] shrink-0 bg-sage" />
      <button
        type="button"
        onClick={onJump}
        className="flex min-w-0 flex-1 items-center gap-3 px-3 py-2 text-left transition hover:bg-sage/5"
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

function MessageBubble({ message, mine, pinned, onPin }) {
  const canPin =
    typeof message.id === 'number' ||
    (typeof message.id === 'string' && !String(message.id).startsWith('pending-'))
  return (
    <div
      id={`coach-msg-${message.id}`}
      className={`group flex ${mine ? 'justify-end' : 'justify-start'}`}
    >
      <div
        className={`max-w-[min(85%,36rem)] px-3.5 py-2 text-sm shadow-sm ${
          mine
            ? 'rounded-2xl rounded-br-md bg-sage text-white'
            : 'rounded-2xl rounded-bl-md border border-[var(--aal-line)] bg-[var(--aal-card)]'
        }`}
      >
        <p className="whitespace-pre-wrap leading-relaxed">{message.content}</p>
        <div
          className={`mt-1 flex items-center gap-2 text-[10px] ${
            mine ? 'justify-end text-white/70' : 'text-[var(--aal-muted)]'
          }`}
        >
          <span>{timeLabel(message.created_at)}</span>
          {canPin ? (
            <button
              type="button"
              onClick={onPin}
              className={`inline-flex items-center gap-1 rounded-md px-1 py-0.5 transition ${
                pinned
                  ? mine
                    ? 'text-white'
                    : 'text-sage'
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
}) {
  const [draft, setDraft] = useState('')
  const [pins, setPins] = useState(() => loadPins(profileId))
  const listRef = useRef(null)
  const inputRef = useRef(null)
  const stickToBottom = useRef(true)
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
    const node = listRef.current
    if (!node || !stickToBottom.current) return
    node.scrollTop = node.scrollHeight
  }, [messages.length, sending])

  function resizeInput() {
    const node = inputRef.current
    if (!node) return
    node.style.height = 'auto'
    node.style.height = `${Math.min(node.scrollHeight, 120)}px`
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

  return (
    <section className="flex h-full min-h-0 flex-col overflow-hidden rounded-2xl border border-[var(--aal-line)] bg-[var(--aal-card)] shadow-sm">
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

      <div
        ref={listRef}
        onScroll={(event) => {
          stickToBottom.current = isNearBottom(event.currentTarget)
        }}
        className="coach-chat-canvas min-h-0 flex-1 space-y-3 overflow-y-auto overscroll-contain px-3 py-4 sm:px-4"
      >
        {weekStart ? (
          <div id="coach-week-artifact">
            <WeekPlan
              plan={plan}
              weekStart={weekStart}
              loading={false}
              generating={generating}
              embedded
              pinned={pins.some((pin) => pin.id === weekPinId)}
              onPin={() => togglePin(pinFromWeek(plan, weekStart))}
            />
          </div>
        ) : null}

        {messages.length === 0 ? (
          <div className="flex h-full min-h-40 flex-col items-center justify-center px-6 text-center">
            <p className="text-sm text-[var(--aal-muted)]">
              Ask about today, remaining days, or how you feel.
            </p>
            <div className="mt-4 flex flex-wrap justify-center gap-2">
              {PROMPTS.map((prompt) => (
                <button
                  key={prompt}
                  type="button"
                  disabled={disabled || sending}
                  onClick={() => submit(prompt)}
                  className="rounded-full border border-[var(--aal-line)] bg-[var(--aal-card)] px-3 py-1.5 text-xs text-[var(--aal-muted)] transition hover:border-sage/50 hover:text-[var(--aal-ink)] disabled:opacity-60"
                >
                  {prompt}
                </button>
              ))}
            </div>
          </div>
        ) : (
          messages.map((message) => {
            const mine = message.role === 'user'
            const pinId = `msg-${message.id}`
            return (
              <MessageBubble
                key={message.id}
                message={message}
                mine={mine}
                pinned={pins.some((pin) => pin.id === pinId)}
                onPin={() => togglePin(pinFromMessage(message))}
              />
            )
          })
        )}
        {sending ? (
          <p className="px-1 text-sm text-[var(--aal-muted)]">Coach is thinking…</p>
        ) : null}
      </div>

      <form
        className="shrink-0 border-t border-[var(--aal-line)] bg-[var(--aal-card)] px-3 py-2.5 sm:px-4"
        onSubmit={(event) => {
          event.preventDefault()
          submit()
        }}
      >
        <div className="flex items-end gap-2">
          <div className="flex min-h-11 flex-1 items-end rounded-[1.6rem] border border-[var(--aal-line)] bg-[var(--aal-bg)] px-4 py-2 focus-within:border-sage/55">
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
              placeholder={disabled ? disabledReason : 'Message'}
              className="max-h-28 min-h-6 w-full resize-none bg-transparent text-sm leading-6 outline-none"
            />
          </div>
          <button
            type="submit"
            disabled={disabled || sending || !draft.trim()}
            className="inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-sage text-white shadow-sm transition hover:brightness-105 disabled:opacity-45"
            aria-label="Send"
          >
            <Send className="h-4 w-4" />
          </button>
        </div>
        <p className="mt-1.5 px-1 text-[10px] text-[var(--aal-muted)]">
          Coaching only — not medical advice.
        </p>
      </form>
    </section>
  )
}
