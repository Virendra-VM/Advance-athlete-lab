import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import {
  clearStoredToken,
  fetchMe,
  getStoredToken,
  login as apiLogin,
  register as apiRegister,
  setStoredToken,
  submitOnboarding as apiSubmitOnboarding,
  updateProfile as apiUpdateProfile,
  completeStravaOnboarding,
  completeCorosOnboarding,
} from '../api/auth'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [token, setToken] = useState(getStoredToken())
  const [loading, setLoading] = useState(true)

  const refreshUser = useCallback(async (activeToken = token) => {
    if (!activeToken) {
      setUser(null)
      return null
    }
    const me = await fetchMe(activeToken)
    setUser(me)
    return me
  }, [token])

  useEffect(() => {
    async function bootstrap() {
      const stored = getStoredToken()
      if (!stored) {
        setLoading(false)
        return
      }
      try {
        setToken(stored)
        await refreshUser(stored)
      } catch {
        clearStoredToken()
        setToken(null)
        setUser(null)
      } finally {
        setLoading(false)
      }
    }
    bootstrap()
  }, [refreshUser])

  async function login(credentials, { remember = true } = {}) {
    const data = await apiLogin(credentials)
    setStoredToken(data.access_token, remember)
    setToken(data.access_token)
    setUser(data.user)
    return data.user
  }

  async function register(payload, { remember = true } = {}) {
    const data = await apiRegister(payload)
    setStoredToken(data.access_token, remember)
    setToken(data.access_token)
    setUser(data.user)
    return data.user
  }

  function logout() {
    clearStoredToken()
    setToken(null)
    setUser(null)
  }

  async function updateProfile(payload) {
    const updated = await apiUpdateProfile(payload, token)
    setUser(updated)
    return updated
  }

  async function submitOnboarding(payload) {
    const updated = await apiSubmitOnboarding(payload, token)
    setUser(updated)
    return updated
  }

  const markStravaOnboardingDone = useCallback(async () => {
    const updated = await completeStravaOnboarding(token)
    setUser(updated)
    return updated
  }, [token])

  const markCorosOnboardingDone = useCallback(async () => {
    const updated = await completeCorosOnboarding(token)
    setUser(updated)
    return updated
  }, [token])

  const value = useMemo(
    () => ({
      user,
      token,
      loading,
      login,
      register,
      logout,
      refreshUser,
      updateProfile,
      submitOnboarding,
      markStravaOnboardingDone,
      markCorosOnboardingDone,
      profile: user?.profile ?? null,
      isAuthenticated: Boolean(token && user),
      needsOnboarding: Boolean(user?.profile && !user.profile.onboarding_completed),
      needsStravaStep: Boolean(
        user?.profile?.onboarding_completed && !user.profile.strava_onboarding_done,
      ),
      needsCorosStep: Boolean(
        user?.profile?.onboarding_completed &&
          user.profile.strava_onboarding_done &&
          !user.profile.coros_onboarding_done,
      ),
    }),
    [user, token, loading, refreshUser, markStravaOnboardingDone, markCorosOnboardingDone],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth must be used within AuthProvider')
  return context
}
