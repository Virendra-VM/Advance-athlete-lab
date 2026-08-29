/** Derive stream averages and elevation from activity points. */
export function computeStreamStats(points = []) {
  const hrs = []
  const powers = []
  const cadences = []
  const speeds = []
  let elevGain = 0
  let prevAlt = null

  for (const point of points) {
    if (point.heart_rate != null) hrs.push(Number(point.heart_rate))
    if (point.power != null) powers.push(Number(point.power))
    if (point.cadence != null) cadences.push(Number(point.cadence))
    if (point.speed_mps != null) speeds.push(Number(point.speed_mps) * 3.6)
    if (point.altitude_m != null) {
      const alt = Number(point.altitude_m)
      if (prevAlt != null && alt > prevAlt) elevGain += alt - prevAlt
      prevAlt = alt
    }
  }

  const avg = (arr) => (arr.length ? arr.reduce((a, b) => a + b, 0) / arr.length : null)
  const max = (arr) => (arr.length ? Math.max(...arr) : null)

  return {
    avgHr: avg(hrs),
    maxHr: max(hrs),
    avgPower: avg(powers),
    maxPower: max(powers),
    avgCadence: avg(cadences),
    avgSpeedKmh: avg(speeds),
    elevGainM: elevGain,
    hasPower: powers.length > 0,
    hasCadence: cadences.length > 0,
    hasHr: hrs.length > 0,
    hasElevation: prevAlt != null,
  }
}

export function downsamplePoints(points, maxPoints = 800) {
  if (!points?.length || points.length <= maxPoints) return points || []
  const step = Math.ceil(points.length / maxPoints)
  return points.filter((_, index) => index % step === 0 || index === points.length - 1)
}
