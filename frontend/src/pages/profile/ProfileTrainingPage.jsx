import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import ProfileEventsPanel from '../../components/season/ProfileEventsPanel'
import ProfileFieldRenderer from '../../components/profile/ProfileFieldRenderer'
import ProfileShell from '../../components/profile/ProfileShell'
import {
  ProfileTip,
  SectionEditButton,
  TrainingView,
} from '../../components/profile/ProfileParts'
import SectionCard from '../../components/ui/SectionCard'
import { useProfileEditor } from '../../context/ProfileEditorContext'
import { FITNESS_FIELDS, GOAL_FIELDS, TIME_FIELDS } from '../../utils/profileForm'

const fadeUp = {
  hidden: { opacity: 0, y: 10 },
  show: { opacity: 1, y: 0, transition: { duration: 0.35, ease: 'easeOut' } },
}

function EditBlock({ title, description, children, className = '' }) {
  return (
    <div
      className={`rounded-2xl border border-[var(--aal-line)] bg-[var(--aal-bg)]/40 p-5 ${className}`}
    >
      <h3 className="text-sm font-semibold text-[var(--aal-ink)]">{title}</h3>
      {description ? (
        <p className="mt-1 text-xs leading-relaxed text-[var(--aal-muted)]">{description}</p>
      ) : null}
      <div className="mt-4">{children}</div>
    </div>
  )
}

export default function ProfileTrainingPage() {
  const { form, isSectionEditing, startSectionEdit } = useProfileEditor()
  const editing = isSectionEditing('training')

  return (
    <ProfileShell
      title="Training"
      subtitle="What you are training for, your current fitness, and the week you can realistically keep."
      actions={
        <SectionEditButton editing={editing} onEdit={() => startSectionEdit('training')} />
      }
    >
      <ProfileTip>
        This is the foundation your coach uses for weekly plans and season structure. Be honest about
        time and fitness — it leads to better sessions.
      </ProfileTip>

      <motion.div initial="hidden" animate="show" variants={fadeUp} className="space-y-5">
        {editing ? (
          <SectionCard title="Edit training profile" subtitle="Grouped by topic so nothing gets missed.">
            <div className="grid gap-5 xl:grid-cols-2">
              <EditBlock title="Goals & event" description="Your north star for the season.">
                <ProfileFieldRenderer fields={GOAL_FIELDS} />
              </EditBlock>
              <EditBlock title="Fitness & load" description="Where you are today — volume, history, recent PRs.">
                <ProfileFieldRenderer fields={FITNESS_FIELDS} />
              </EditBlock>
              <EditBlock
                title="Weekly schedule"
                description="Days, session length, and preferred time."
                className="xl:col-span-2"
              >
                <ProfileFieldRenderer fields={TIME_FIELDS} columns="md:grid-cols-2 xl:grid-cols-4" />
              </EditBlock>
              <p className="text-sm text-[var(--aal-muted)]">
                Power and heart-rate anchors live in{' '}
                <Link to="/profile/zones" className="font-semibold text-sage hover:underline">
                  Training zones
                </Link>
                .
              </p>
            </div>
          </SectionCard>
        ) : (
          <div className="grid gap-5 xl:grid-cols-2">
            <SectionCard
              title="Goals & fitness"
              subtitle="What you want and where you are starting from."
              dense
            >
              <TrainingView form={form} middleContent={null} leadingOnly />
            </SectionCard>

            <SectionCard title="Schedule & load" subtitle="The week your coach will plan around." dense>
              <TrainingView form={form} trailingOnly />
            </SectionCard>

            <SectionCard
              title="Season races"
              subtitle="A-race and B-races that shape your plan."
              dense
              className="xl:col-span-2"
            >
              <ProfileEventsPanel inTraining />
            </SectionCard>
          </div>
        )}
      </motion.div>
    </ProfileShell>
  )
}
