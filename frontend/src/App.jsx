import { Navigate, Route, Routes } from 'react-router-dom'
import { AuthProvider, useAuth } from './context/AuthContext'
import ActivityDetailPage from './components/ActivityDetailPage'
import ConnectCoros from './components/ConnectCoros'
import ConnectStrava from './components/ConnectStrava'
import CorosCallback from './components/CorosCallback'
import Dashboard from './components/Dashboard'
import OnboardingWizard from './components/OnboardingWizard'
import ProfilePage from './components/ProfilePage'
import SettingsPage from './components/SettingsPage'
import SignIn from './components/SignIn'
import StravaCallback from './components/StravaCallback'
import ActivitiesPage from './pages/ActivitiesPage'
import CoachPage from './pages/CoachPage'
import SchedulePage from './pages/SchedulePage'
import VolumePage from './pages/VolumePage'
import {
  DailyHealthPage,
  FitnessPage,
  HrvPage,
  RecoveryPage,
  RhrPage,
  SleepPage,
  StressPage,
  TrainingLoadPage,
} from './pages/healthPages'

function HomeRedirect() {
  const { isAuthenticated, loading, needsOnboarding, needsStravaStep, needsCorosStep } = useAuth()
  if (loading) return null
  if (!isAuthenticated) return <Navigate to="/signin" replace />
  if (needsOnboarding) return <Navigate to="/onboarding" replace />
  if (needsStravaStep) return <Navigate to="/connect-strava" replace />
  if (needsCorosStep) return <Navigate to="/connect-coros" replace />
  return <Navigate to="/dashboard" replace />
}

function ProtectedRoute({ children }) {
  const { isAuthenticated, loading, needsOnboarding, needsStravaStep } = useAuth()
  if (loading) return null
  if (!isAuthenticated) return <Navigate to="/signin" replace />
  if (needsOnboarding) return <Navigate to="/onboarding" replace />
  if (needsStravaStep) return <Navigate to="/connect-strava" replace />
  return children
}

function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<HomeRedirect />} />
      <Route path="/signin" element={<SignIn />} />
      <Route path="/onboarding" element={<OnboardingWizard />} />
      <Route path="/connect-strava" element={<ConnectStrava />} />
      <Route path="/connect-coros" element={<ConnectCoros />} />
      <Route path="/dashboard" element={<ProtectedRoute><Dashboard /></ProtectedRoute>} />
      <Route path="/health/recovery" element={<ProtectedRoute><RecoveryPage /></ProtectedRoute>} />
      <Route path="/health/sleep" element={<ProtectedRoute><SleepPage /></ProtectedRoute>} />
      <Route path="/health/hrv" element={<ProtectedRoute><HrvPage /></ProtectedRoute>} />
      <Route path="/health/stress" element={<ProtectedRoute><StressPage /></ProtectedRoute>} />
      <Route path="/health/rhr" element={<ProtectedRoute><RhrPage /></ProtectedRoute>} />
      <Route path="/health/daily" element={<ProtectedRoute><DailyHealthPage /></ProtectedRoute>} />
      <Route path="/training/load" element={<ProtectedRoute><TrainingLoadPage /></ProtectedRoute>} />
      <Route path="/training/volume" element={<ProtectedRoute><VolumePage /></ProtectedRoute>} />
      <Route path="/training/fitness" element={<ProtectedRoute><FitnessPage /></ProtectedRoute>} />
      <Route path="/training/schedule" element={<ProtectedRoute><SchedulePage /></ProtectedRoute>} />
      <Route path="/activities" element={<ProtectedRoute><ActivitiesPage /></ProtectedRoute>} />
      <Route path="/coach" element={<ProtectedRoute><CoachPage /></ProtectedRoute>} />
      <Route path="/profile" element={<ProtectedRoute><ProfilePage /></ProtectedRoute>} />
      <Route path="/settings" element={<ProtectedRoute><SettingsPage /></ProtectedRoute>} />
      <Route
        path="/activities/:activityId"
        element={<ProtectedRoute><ActivityDetailPage /></ProtectedRoute>}
      />
      <Route path="/oauth/strava/callback" element={<StravaCallback />} />
      <Route path="/oauth/coros/callback" element={<CorosCallback />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

export default function App() {
  return (
    <AuthProvider>
      <AppRoutes />
    </AuthProvider>
  )
}
