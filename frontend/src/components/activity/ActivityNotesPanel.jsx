import { useEffect, useState } from 'react'
import { Check, Pencil, Plus, Trash2, X } from 'lucide-react'
import {
  createActivityNote,
  deleteActivityNote,
  listActivityNotes,
  updateActivityNote,
} from '../../api/activities'
import { formatClockTime, formatDate, parseUtcDate } from '../../utils/formatters'
import LoadingDots from '../ui/LoadingDots'
import { EmptyDetailState } from './detailShared'

function noteTimestamp(note) {
  const created = parseUtcDate(note.created_at)
  const updated = parseUtcDate(note.updated_at)
  const createdLabel = `${formatDate(created)} · ${formatClockTime(created)}`
  if (!created) return '—'
  if (!updated) return `Added ${createdLabel}`
  const edited = updated.getTime() - created.getTime() > 2000
  if (!edited) return `Added ${createdLabel}`
  return `Added ${createdLabel} · Edited ${formatDate(updated)} · ${formatClockTime(updated)}`
}

export default function ActivityNotesPanel({ activityId }) {
  const [notes, setNotes] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [composing, setComposing] = useState(false)
  const [draft, setDraft] = useState('')
  const [editingId, setEditingId] = useState(null)
  const [editDraft, setEditDraft] = useState('')
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    let cancelled = false
    async function load() {
      setLoading(true)
      setError('')
      try {
        const data = await listActivityNotes(activityId)
        if (!cancelled) setNotes(data.items || [])
      } catch (err) {
        if (!cancelled) setError(err.message || 'Failed to load notes.')
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    load()
    return () => {
      cancelled = true
    }
  }, [activityId])

  async function handleCreate() {
    const body = draft.trim()
    if (!body) return
    setSaving(true)
    setError('')
    try {
      const created = await createActivityNote(activityId, body)
      setNotes((prev) => [created, ...prev])
      setDraft('')
      setComposing(false)
    } catch (err) {
      setError(err.message || 'Failed to add note.')
    } finally {
      setSaving(false)
    }
  }

  async function handleUpdate(noteId) {
    const body = editDraft.trim()
    if (!body) return
    setSaving(true)
    setError('')
    try {
      const updated = await updateActivityNote(activityId, noteId, body)
      setNotes((prev) => prev.map((note) => (note.id === noteId ? updated : note)))
      setEditingId(null)
      setEditDraft('')
    } catch (err) {
      setError(err.message || 'Failed to update note.')
    } finally {
      setSaving(false)
    }
  }

  async function handleDelete(noteId) {
    if (!window.confirm('Delete this note?')) return
    setSaving(true)
    setError('')
    try {
      await deleteActivityNote(activityId, noteId)
      setNotes((prev) => prev.filter((note) => note.id !== noteId))
      if (editingId === noteId) {
        setEditingId(null)
        setEditDraft('')
      }
    } catch (err) {
      setError(err.message || 'Failed to delete note.')
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return (
      <div className="rounded-xl border border-[var(--aal-line)] bg-[var(--aal-card)] p-6">
        <LoadingDots label="Loading notes…" />
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-[var(--aal-ink)]">Notes</h2>
          <p className="text-xs text-[var(--aal-muted)]">
            {notes.length} note{notes.length === 1 ? '' : 's'} on this activity
          </p>
        </div>
        {!composing ? (
          <button
            type="button"
            onClick={() => setComposing(true)}
            className="inline-flex h-9 items-center gap-1.5 rounded-xl bg-sage px-3 text-sm font-semibold text-white"
          >
            <Plus className="h-4 w-4" />
            Add note
          </button>
        ) : null}
      </div>

      {error ? <p className="text-sm text-danger-muted">{error}</p> : null}

      {composing ? (
        <div className="rounded-xl border border-[var(--aal-line)] bg-[var(--aal-card)] p-4">
          <textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            rows={4}
            autoFocus
            placeholder="Write a note about this workout…"
            className="w-full rounded-xl border border-[var(--aal-line)] bg-[var(--aal-bg)] px-3 py-2 text-sm outline-none focus:border-sage"
          />
          <div className="mt-3 flex flex-wrap gap-2">
            <button
              type="button"
              disabled={saving || !draft.trim()}
              onClick={handleCreate}
              className="inline-flex h-9 items-center gap-1.5 rounded-xl bg-sage px-3 text-sm font-semibold text-white disabled:opacity-60"
            >
              <Check className="h-4 w-4" />
              Save
            </button>
            <button
              type="button"
              disabled={saving}
              onClick={() => {
                setComposing(false)
                setDraft('')
              }}
              className="inline-flex h-9 items-center gap-1.5 rounded-xl border border-[var(--aal-line)] px-3 text-sm font-medium"
            >
              <X className="h-4 w-4" />
              Cancel
            </button>
          </div>
        </div>
      ) : null}

      {!notes.length && !composing ? (
        <EmptyDetailState
          title="No notes yet"
          body="Add coaching cues, how the session felt, or anything you want to remember."
        />
      ) : null}

      <ul className="space-y-3">
        {notes.map((note) => (
          <li
            key={note.id}
            className="rounded-xl border border-[var(--aal-line)] bg-[var(--aal-card)] p-4"
          >
            {editingId === note.id ? (
              <>
                <textarea
                  value={editDraft}
                  onChange={(e) => setEditDraft(e.target.value)}
                  rows={4}
                  className="w-full rounded-xl border border-[var(--aal-line)] bg-[var(--aal-bg)] px-3 py-2 text-sm outline-none focus:border-sage"
                />
                <div className="mt-3 flex flex-wrap gap-2">
                  <button
                    type="button"
                    disabled={saving || !editDraft.trim()}
                    onClick={() => handleUpdate(note.id)}
                    className="inline-flex h-9 items-center gap-1.5 rounded-xl bg-sage px-3 text-sm font-semibold text-white disabled:opacity-60"
                  >
                    <Check className="h-4 w-4" />
                    Save
                  </button>
                  <button
                    type="button"
                    disabled={saving}
                    onClick={() => {
                      setEditingId(null)
                      setEditDraft('')
                    }}
                    className="inline-flex h-9 items-center gap-1.5 rounded-xl border border-[var(--aal-line)] px-3 text-sm font-medium"
                  >
                    <X className="h-4 w-4" />
                    Cancel
                  </button>
                </div>
              </>
            ) : (
              <>
                <div className="flex items-start justify-between gap-3">
                  <p className="whitespace-pre-wrap text-sm text-[var(--aal-ink)]">{note.body}</p>
                  <div className="flex shrink-0 gap-1">
                    <button
                      type="button"
                      title="Edit note"
                      onClick={() => {
                        setEditingId(note.id)
                        setEditDraft(note.body)
                      }}
                      className="rounded-lg p-2 text-[var(--aal-muted)] hover:bg-[var(--aal-accent-soft)] hover:text-[var(--aal-ink)]"
                    >
                      <Pencil className="h-4 w-4" />
                    </button>
                    <button
                      type="button"
                      title="Delete note"
                      onClick={() => handleDelete(note.id)}
                      className="rounded-lg p-2 text-[var(--aal-muted)] hover:bg-red-500/10 hover:text-red-500"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                </div>
                <p className="mt-2 text-[11px] text-[var(--aal-muted)]">{noteTimestamp(note)}</p>
              </>
            )}
          </li>
        ))}
      </ul>
    </div>
  )
}
