import { createBrowserRouter, Navigate, Outlet, RouterProvider } from 'react-router-dom'
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
import VerifyEmailPage from './pages/VerifyEmailPage'
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

function AppLayout() {
  return (
    <AuthProvider>
      <Outlet />
    </AuthProvider>
  )
}

const router = createBrowserRouter([
  {
    element: <AppLayout />,
    children: [
      { path: '/', element: <HomeRedirect /> },
      { path: '/signin', element: <SignIn /> },
      { path: '/onboarding', element: <OnboardingWizard /> },
      { path: '/verify-email', element: <VerifyEmailPage /> },
      { path: '/connect-strava', element: <ConnectStrava /> },
      { path: '/connect-coros', element: <ConnectCoros /> },
      {
        path: '/dashboard',
        element: (
          <ProtectedRoute>
            <Dashboard />
          </ProtectedRoute>
        ),
      },
      {
        path: '/health/recovery',
        element: (
          <ProtectedRoute>
            <RecoveryPage />
          </ProtectedRoute>
        ),
      },
      {
        path: '/health/sleep',
        element: (
          <ProtectedRoute>
            <SleepPage />
          </ProtectedRoute>
        ),
      },
      {
        path: '/health/hrv',
        element: (
          <ProtectedRoute>
            <HrvPage />
          </ProtectedRoute>
        ),
      },
      {
        path: '/health/stress',
        element: (
          <ProtectedRoute>
            <StressPage />
          </ProtectedRoute>
        ),
      },
      {
        path: '/health/rhr',
        element: (
          <ProtectedRoute>
            <RhrPage />
          </ProtectedRoute>
        ),
      },
      {
        path: '/health/daily',
        element: (
          <ProtectedRoute>
            <DailyHealthPage />
          </ProtectedRoute>
        ),
      },
      {
        path: '/training/load',
        element: (
          <ProtectedRoute>
            <TrainingLoadPage />
          </ProtectedRoute>
        ),
      },
      {
        path: '/training/volume',
        element: (
          <ProtectedRoute>
            <VolumePage />
          </ProtectedRoute>
        ),
      },
      {
        path: '/training/fitness',
        element: (
          <ProtectedRoute>
            <FitnessPage />
          </ProtectedRoute>
        ),
      },
      {
        path: '/training/schedule',
        element: (
          <ProtectedRoute>
            <SchedulePage />
          </ProtectedRoute>
        ),
      },
      {
        path: '/activities',
        element: (
          <ProtectedRoute>
            <ActivitiesPage />
          </ProtectedRoute>
        ),
      },
      {
        path: '/coach',
        element: (
          <ProtectedRoute>
            <CoachPage />
          </ProtectedRoute>
        ),
      },
      {
        path: '/profile',
        element: (
          <ProtectedRoute>
            <ProfilePage />
          </ProtectedRoute>
        ),
      },
      {
        path: '/settings',
        element: (
          <ProtectedRoute>
            <SettingsPage />
          </ProtectedRoute>
        ),
      },
      {
        path: '/activities/:activityId',
        element: (
          <ProtectedRoute>
            <ActivityDetailPage />
          </ProtectedRoute>
        ),
      },
      { path: '/oauth/strava/callback', element: <StravaCallback /> },
      { path: '/oauth/coros/callback', element: <CorosCallback /> },
      { path: '*', element: <Navigate to="/" replace /> },
    ],
  },
])

export default function App() {
  return <RouterProvider router={router} />
}
