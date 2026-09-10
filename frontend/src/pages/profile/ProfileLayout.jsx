import { useEffect } from 'react'
import { Navigate, Outlet, useLocation, useNavigate } from 'react-router-dom'
import AppShell from '../../components/layout/AppShell'
import ProfileSectionNav from '../../components/profile/ProfileSectionNav'
import { useAuth } from '../../context/AuthContext'
import { ProfileEditorProvider, useProfileEditor } from '../../context/ProfileEditorContext'
import { LeaveGuard, StickySaveBar } from '../../components/profile/ProfileParts'
import { legacyProfilePathFromHash } from '../../utils/profileView'

function ProfileLayoutInner() {
  const location = useLocation()
  const navigate = useNavigate()
  const { isAuthenticated } = useAuth()
  const {
    form,
    dirty,
    isEditing,
    saving,
    message,
    error,
    blocker,
    handleSave,
    stopEditing,
    discardChanges,
  } = useProfileEditor()

  useEffect(() => {
    const target = legacyProfilePathFromHash(location.hash)
    if (!target) return
    const [pathname, hash = ''] = target.split('#')
    const nextHash = hash ? `#${hash}` : ''
    if (pathname !== location.pathname || nextHash !== location.hash) {
      navigate({ pathname, hash: nextHash }, { replace: true })
    }
  }, [location.hash, location.pathname, navigate])

  if (!isAuthenticated) return <Navigate to="/signin" replace />
  if (!form) {
    return (
      <div className="flex min-h-[40vh] items-center justify-center px-4">
        <p className="text-sm text-[var(--aal-muted)]">Loading profile…</p>
      </div>
    )
  }

  return (
    <>
      <form onSubmit={handleSave} className="flex h-full min-h-0 flex-col">
        <div className="min-h-0 flex-1 overflow-y-auto px-4 sm:px-6 lg:px-8 lg:pt-6">
          <div className="border-b border-[var(--aal-line)] pb-4">
            <ProfileSectionNav />
          </div>

          <div className="space-y-6 py-5">
            <Outlet />
            {!isEditing && message ? (
              <p className="text-sm text-sage">{message}</p>
            ) : null}
          </div>
        </div>

        {isEditing ? (
          <StickySaveBar
            dirty={dirty}
            saving={saving}
            message={message}
            error={error}
            onDone={stopEditing}
            onDiscard={discardChanges}
          />
        ) : null}
      </form>
      <LeaveGuard
        open={blocker.state === 'blocked'}
        onStay={() => blocker.reset?.()}
        onLeave={() => blocker.proceed?.()}
      />
    </>
  )
}

export default function ProfileLayout() {
  return (
    <AppShell title="Profile" fill>
      <ProfileEditorProvider>
        <ProfileLayoutInner />
      </ProfileEditorProvider>
    </AppShell>
  )
}
