import OnboardingField from '../onboarding/OnboardingFields'
import { useProfileEditor } from '../../context/ProfileEditorContext'

export default function ProfileFieldRenderer({ fields, columns = 'md:grid-cols-2' }) {
  const { form, updateField } = useProfileEditor()

  return (
    <div className={`grid gap-6 ${columns}`}>
      {fields.map((field) => (
        <div
          key={field.key}
          className={
            field.type === 'chips-single' ||
            field.type === 'chips-multi' ||
            field.type === 'textarea' ||
            field.type === 'weekly-volume'
              ? 'md:col-span-2'
              : ''
          }
        >
          <OnboardingField
            field={field}
            answers={form}
            value={form[field.key]}
            onChange={(value) => updateField(field.key, value)}
          />
        </div>
      ))}
    </div>
  )
}
