import { createContext, useContext, useEffect, useMemo, useState } from 'react'
import { useBlocker } from 'react-router-dom'
import { useAuth } from './AuthContext'
import { getCycleContext } from '../api/cycle'
import { buildProfileForm, buildProfileSavePayload } from '../utils/profileForm'
import { formsEqual } from '../utils/profileView'

const ProfileEditorContext = createContext(null)

export function ProfileEditorProvider({ children }) {
  const { profile, updateProfile, refreshUser } = useAuth()
  const savedForm = useMemo(() => buildProfileForm(profile), [profile])
  const [draft, setDraft] = useState(null)
  const [editingAll, setEditingAll] = useState(false)
  const [editingSections, setEditingSections] = useState(() => new Set())
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [cycleContext, setCycleContext] = useState(null)

  const form = draft ?? savedForm
  const dirty = Boolean(draft && savedForm && !formsEqual(draft, savedForm))
  const isEditing = editingAll || editingSections.size > 0

  const blocker = useBlocker(
    ({ currentLocation, nextLocation }) =>
      dirty && currentLocation.pathname !== nextLocation.pathname,
  )

  useEffect(() => {
    if (!savedForm?.cycle_tracking_enabled) return undefined
    let cancelled = false
    getCycleContext()
      .then((result) => {
        if (!cancelled) setCycleContext(result)
      })
      .catch(() => {
        if (!cancelled) setCycleContext(null)
      })
    return () => {
      cancelled = true
    }
  }, [savedForm?.cycle_tracking_enabled])

  useEffect(() => {
    if (!dirty) return undefined
    function onBeforeUnload(event) {
      event.preventDefault()
      event.returnValue = ''
    }
    window.addEventListener('beforeunload', onBeforeUnload)
    return () => window.removeEventListener('beforeunload', onBeforeUnload)
  }, [dirty])

  function isSectionEditing(id) {
    return editingAll || editingSections.has(id)
  }

  function startSectionEdit(id) {
    setMessage('')
    setEditingSections((prev) => new Set(prev).add(id))
  }

  function startAllEdit() {
    setMessage('')
    setEditingAll(true)
  }

  function stopEditing() {
    setEditingAll(false)
    setEditingSections(new Set())
  }

  function discardChanges() {
    setDraft(null)
    setError('')
    setMessage('')
    stopEditing()
  }

  function updateField(key, value) {
    setDraft((prev) => ({ ...(prev ?? savedForm), [key]: value }))
    setMessage('')
  }

  async function handleSave(event) {
    event?.preventDefault()
    if (!dirty) {
      stopEditing()
      return
    }
    setSaving(true)
    setError('')
    setMessage('')
    try {
      const updated = await updateProfile(buildProfileSavePayload(form))
      const next = buildProfileForm(updated?.profile)
      if (!next) throw new Error('Profile did not update.')
      setDraft(null)
      stopEditing()
      setMessage('Saved. Your coach will use this on the next plan.')
    } catch (err) {
      setError(err.message || 'Failed to save profile.')
    } finally {
      setSaving(false)
    }
  }

  async function handleEstimateApplied() {
    await refreshUser()
    setDraft(null)
    stopEditing()
  }

  const value = {
    form,
    savedForm,
    dirty,
    isEditing,
    saving,
    message,
    error,
    cycleContext,
    setCycleContext,
    blocker,
    isSectionEditing,
    startSectionEdit,
    startAllEdit,
    stopEditing,
    discardChanges,
    updateField,
    handleSave,
    handleEstimateApplied,
  }

  return (
    <ProfileEditorContext.Provider value={value}>{children}</ProfileEditorContext.Provider>
  )
}

export function useProfileEditor() {
  const context = useContext(ProfileEditorContext)
  if (!context) {
    throw new Error('useProfileEditor must be used within ProfileEditorProvider')
  }
  return context
}
