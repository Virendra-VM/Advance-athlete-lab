import OnboardingField from '../onboarding/OnboardingFields'
import CycleTrackingFields, { CycleTrackingView } from './CycleTrackingPanel'
import ProfileFieldRenderer from './ProfileFieldRenderer'
import {
  BodyView,
  HealthView,
  MeasureFields,
  PlanningNotesView,
  PreferencesView,
  SectionEditButton,
} from './ProfileParts'
import SectionCard from '../ui/SectionCard'
import { useProfileEditor } from '../../context/ProfileEditorContext'
import { BODY_FIELDS, PREFERENCE_FIELDS } from '../../utils/profileForm'

export default function ProfileAthleteDetailsSections() {
  const {
    form,
    cycleContext,
    setCycleContext,
    isSectionEditing,
    startSectionEdit,
    updateField,
  } = useProfileEditor()

  return (
    <div className="grid gap-5 xl:grid-cols-2">
      <SectionCard
        id="profile-body"
        title="Body"
        subtitle="Age, height, weight, and units — used for load and pacing."
        actions={
          <SectionEditButton
            editing={isSectionEditing('body')}
            onEdit={() => startSectionEdit('body')}
          />
        }
      >
        {isSectionEditing('body') ? (
          <div className="space-y-6">
            <ProfileFieldRenderer fields={BODY_FIELDS} />
            <MeasureFields form={form} onChange={updateField} />
          </div>
        ) : (
          <BodyView form={form} />
        )}
      </SectionCard>

      <SectionCard
        id="profile-health"
        title="Health & injuries"
        subtitle="What your coach should train around — past and current."
        actions={
          <SectionEditButton
            editing={isSectionEditing('health')}
            onEdit={() => startSectionEdit('health')}
          />
        }
      >
        {isSectionEditing('health') ? (
          <div>
            <OnboardingField
              field={{ key: 'injuries', type: 'injuries' }}
              answers={form}
              value={form.injuries}
              onChange={(value) => updateField('injuries', value)}
            />
            <div className="mt-6">
              <OnboardingField
                field={{
                  key: 'injuries_limitations',
                  label: 'Anything else to avoid',
                  type: 'textarea',
                }}
                answers={form}
                value={form.injuries_limitations}
                onChange={(value) => updateField('injuries_limitations', value)}
              />
            </div>
            <CycleTrackingFields
              form={form}
              onChange={updateField}
              onCycleUpdate={setCycleContext}
            />
          </div>
        ) : (
          <>
            <HealthView form={form} />
            <div className="mt-6">
              <CycleTrackingView form={form} cycleContext={cycleContext} />
            </div>
          </>
        )}
      </SectionCard>

      <SectionCard
        id="profile-preferences"
        title="Preferences"
        subtitle="Gear you have access to and sessions you love or hate."
        actions={
          <SectionEditButton
            editing={isSectionEditing('preferences')}
            onEdit={() => startSectionEdit('preferences')}
          />
        }
      >
        {isSectionEditing('preferences') ? (
          <ProfileFieldRenderer fields={PREFERENCE_FIELDS} />
        ) : (
          <PreferencesView form={form} />
        )}
      </SectionCard>

      <SectionCard
        id="profile-planning"
        title="Coach notes"
        subtitle="Travel, schedule quirks, or anything the structured fields do not capture."
        actions={
          <SectionEditButton
            editing={isSectionEditing('planning')}
            onEdit={() => startSectionEdit('planning')}
          />
        }
      >
        {isSectionEditing('planning') ? (
          <OnboardingField
            field={{
              key: 'planning_notes',
              label: 'Notes for your coach',
              type: 'textarea',
              placeholder:
                'e.g. Away 12–18 Oct, can only train mornings, prefer long run on Sunday…',
            }}
            answers={form}
            value={form.planning_notes}
            onChange={(value) => updateField('planning_notes', value)}
          />
        ) : (
          <PlanningNotesView form={form} />
        )}
      </SectionCard>
    </div>
  )
}
