import { Navigate, Route, Routes } from 'react-router-dom'
import { AuthProvider, useAuth } from './context/AuthContext'
import ActivityDetailPage from './components/ActivityDetailPage'
import ConnectStrava from './components/ConnectStrava'
import Dashboard from './components/Dashboard'
import OnboardingWizard from './components/OnboardingWizard'
import ProfilePage from './components/ProfilePage'
import SettingsPage from './components/SettingsPage'
import SignIn from './components/SignIn'
import StravaCallback from './components/StravaCallback'

function HomeRedirect() {
  const { isAuthenticated, loading, needsOnboarding, needsStravaStep } = useAuth()
  if (loading) return null
  if (!isAuthenticated) return <Navigate to="/signin" replace />
  if (needsOnboarding) return <Navigate to="/onboarding" replace />
  if (needsStravaStep) return <Navigate to="/connect-strava" replace />
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
      <Route
        path="/dashboard"
        element={
          <ProtectedRoute>
            <Dashboard />
          </ProtectedRoute>
        }
      />
      <Route
        path="/profile"
        element={
          <ProtectedRoute>
            <ProfilePage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/settings"
        element={
          <ProtectedRoute>
            <SettingsPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/activities/:activityId"
        element={
          <ProtectedRoute>
            <ActivityDetailPage />
          </ProtectedRoute>
        }
      />
      <Route path="/oauth/strava/callback" element={<StravaCallback />} />
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
