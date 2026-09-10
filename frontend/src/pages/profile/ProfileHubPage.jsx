import { useEffect } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { Pencil, Sparkles } from 'lucide-react'
import UserAvatar from '../../components/UserAvatar'
import OnboardingField from '../../components/onboarding/OnboardingFields'
import ProfileAthleteDetailsSections from '../../components/profile/ProfileAthleteDetailsSections'
import ProfileCompletenessPanel from '../../components/profile/ProfileCompletenessPanel'
import {
  FactStrip,
  IdentityEditFields,
  IdentityFocus,
  SectionEditButton,
  SettingsHint,
  SportPills,
} from '../../components/profile/ProfileParts'
import { useProfileEditor } from '../../context/ProfileEditorContext'
import {
  displayAge,
  goalHeadline,
  profilePathForSection,
  scrollToProfileSection,
  sectionFromHash,
} from '../../utils/profileView'

const fadeUp = {
  hidden: { opacity: 0, y: 10 },
  show: { opacity: 1, y: 0, transition: { duration: 0.35, ease: 'easeOut' } },
}

export default function ProfileHubPage() {
  const location = useLocation()
  const navigate = useNavigate()
  const {
    form,
    isSectionEditing,
    startSectionEdit,
    startAllEdit,
    updateField,
  } = useProfileEditor()

  const headline = goalHeadline(form)

  useEffect(() => {
    const section = sectionFromHash(location.hash)
    if (section) {
      window.setTimeout(() => scrollToProfileSection(section), 80)
    }
  }, [location.hash])

  function jumpToMissing(item) {
    const path = profilePathForSection(item.section)
    if (!path) return
    const [pathname, hash = ''] = path.split('#')
    if (pathname !== location.pathname) {
      navigate({ pathname, hash: hash ? `#${hash}` : '' })
      return
    }
    if (hash) {
      navigate({ pathname, hash: `#${hash}` })
      return
    }
    scrollToProfileSection(item.section)
  }

  return (
    <div className="w-full space-y-6">
      <motion.section
        initial="hidden"
        animate="show"
        variants={fadeUp}
        className="relative overflow-hidden rounded-3xl border border-[var(--aal-line)] bg-[var(--aal-card)]"
      >
        <div
          className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_top_right,_var(--tw-gradient-stops))] from-sage/12 via-transparent to-transparent"
          aria-hidden
        />
        <div className="relative p-6 sm:p-8">
          <div className="flex flex-col gap-6 lg:flex-row lg:items-start lg:justify-between">
            <div className="flex min-w-0 flex-1 flex-col gap-6 sm:flex-row sm:items-start">
              <div className="relative shrink-0">
                <div className="rounded-full ring-4 ring-sage/15 ring-offset-2 ring-offset-[var(--aal-card)]">
                  <UserAvatar letter={form.avatar_letter} name={form.name} size="xl" />
                </div>
              </div>

              <div className="min-w-0 flex-1">
                {isSectionEditing('identity') ? (
                  <IdentityEditFields form={form} onChange={updateField}>
                    <OnboardingField
                      field={{ key: 'sports', label: 'Sports', type: 'sports' }}
                      answers={form}
                      value={form.sports}
                      onChange={(value) => updateField('sports', value)}
                    />
                  </IdentityEditFields>
                ) : (
                  <>
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-sage">
                          Your profile
                        </p>
                        <h1 className="mt-1 font-display text-3xl font-medium tracking-tight text-[var(--aal-ink)] sm:text-4xl">
                          {form.name || 'Athlete'}
                        </h1>
                        {headline ? (
                          <p className="mt-2 flex items-start gap-2 text-sm text-[var(--aal-muted)]">
                            <Sparkles className="mt-0.5 h-4 w-4 shrink-0 text-sage" aria-hidden />
                            <span>{headline}</span>
                          </p>
                        ) : null}
                      </div>
                      <SectionEditButton
                        editing={false}
                        onEdit={() => startSectionEdit('identity')}
                        label="Edit name"
                      />
                    </div>
                    <div className="mt-4">
                      <SportPills sports={form.sports} />
                    </div>
                    <IdentityFocus form={form} />
                  </>
                )}
              </div>
            </div>

            <div className="shrink-0 lg:pt-2">
              <ProfileCompletenessPanel form={form} onJump={jumpToMissing} />
            </div>
          </div>

          <div className="mt-6">
            <FactStrip form={{ ...form, displayAge: displayAge(form) }} />
          </div>

          <div className="mt-6 flex flex-wrap gap-2 border-t border-[var(--aal-line)] pt-5">
            <button
              type="button"
              onClick={startAllEdit}
              className="inline-flex items-center gap-2 rounded-xl bg-sage px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-sage/90"
            >
              <Pencil className="h-4 w-4" />
              Edit all sections
            </button>
          </div>
        </div>
      </motion.section>

      <ProfileAthleteDetailsSections />

      <SettingsHint />
    </div>
  )
}
