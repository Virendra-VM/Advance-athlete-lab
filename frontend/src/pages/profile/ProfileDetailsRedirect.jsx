import { Navigate, useLocation } from 'react-router-dom'

/** Legacy /profile/details → /profile with same hash anchor. */
export default function ProfileDetailsRedirect() {
  const location = useLocation()
  return <Navigate to={`/profile${location.hash}`} replace />
}
