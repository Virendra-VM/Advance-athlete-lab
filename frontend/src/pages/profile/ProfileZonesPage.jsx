import ProfileShell from '../../components/profile/ProfileShell'
import { ProfileTip, SectionEditButton } from '../../components/profile/ProfileParts'
import { TrainingZonesEditor, TrainingZonesView } from '../../components/profile/TrainingZonesSection'
import SectionCard from '../../components/ui/SectionCard'
import { useProfileEditor } from '../../context/ProfileEditorContext'

export default function ProfileZonesPage() {
  const { form, isSectionEditing, startSectionEdit, updateField, handleEstimateApplied } =
    useProfileEditor()
  const editing = isSectionEditing('zones')

  return (
    <ProfileShell
      title="Training zones"
      subtitle="Heart rate, power, and pace ranges — the same anchors your watch uses for structured workouts."
      actions={
        <SectionEditButton editing={editing} onEdit={() => startSectionEdit('zones')} />
      }
    >
      <ProfileTip>
        Set at least one anchor (FTP, LTHR, or threshold pace). The app can suggest values from recent
        tests and races — look for nudges below the zone tables.
      </ProfileTip>

      <SectionCard
        title="Anchors & zone tables"
        subtitle={editing ? 'Update thresholds or apply suggested values.' : 'Live zones from your saved anchors.'}
      >
        {editing ? (
          <TrainingZonesEditor
            form={form}
            onChange={updateField}
            onEstimateApplied={handleEstimateApplied}
          />
        ) : (
          <TrainingZonesView form={form} />
        )}
      </SectionCard>
    </ProfileShell>
  )
}
