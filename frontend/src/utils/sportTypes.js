const SPORT_LABELS = {
  Run: 'Run',
  VirtualRun: 'Run',
  TrailRun: 'Run',
  Ride: 'Bike',
  VirtualRide: 'Bike',
  EBikeRide: 'Bike',
  Swim: 'Swim',
  WeightTraining: 'Strength',
  Workout: 'Workout',
  Walk: 'Walk',
  Hike: 'Hike',
  Yoga: 'Yoga',
  Crossfit: 'CrossFit',
  Rowing: 'Rowing',
  AlpineSki: 'Ski',
  BackcountrySki: 'Ski',
  NordicSki: 'Ski',
  Snowboard: 'Snowboard',
  Elliptical: 'Elliptical',
  StairStepper: 'Stairs',
  RockClimbing: 'Climb',
}

const SPORT_COLORS = {
  Run: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300',
  Bike: 'bg-orange-100 text-orange-700 dark:bg-orange-950/40 dark:text-orange-300',
  Swim: 'bg-blue-100 text-blue-700 dark:bg-blue-950/40 dark:text-blue-300',
  Strength: 'bg-purple-100 text-purple-700 dark:bg-purple-950/40 dark:text-purple-300',
  Walk: 'bg-slate-100 text-slate-700 dark:bg-gray-700 dark:text-slate-300',
  Workout: 'bg-slate-100 text-slate-700 dark:bg-gray-700 dark:text-slate-300',
}

export function formatSportType(sportType) {
  if (!sportType) return 'Workout'
  return SPORT_LABELS[sportType] || sportType.replace(/([a-z])([A-Z])/g, '$1 $2')
}

export function getSportBadgeClass(sportType) {
  const label = formatSportType(sportType)
  return SPORT_COLORS[label] || SPORT_COLORS.Workout
}

export function isGenericActivityName(name) {
  if (!name) return true
  return /^Activity \d+$/.test(name.trim())
}

export function getActivityTitle(activity) {
  const sport = formatSportType(activity.sport_type)
  if (isGenericActivityName(activity.name)) return sport
  return activity.name.trim()
}

export function getActivitySubtitle(activity) {
  if (isGenericActivityName(activity.name)) return null
  return formatSportType(activity.sport_type)
}
