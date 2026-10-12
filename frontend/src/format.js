// Formatos de números y unidades para mostrar (es-AR).

export const M_PER_FT = 0.3048
export const M_PER_NM = 1852
export const KMH_PER_KT = 1.852

const nf0 = new Intl.NumberFormat('es-AR', { maximumFractionDigits: 0 })
const nf1 = new Intl.NumberFormat('es-AR', { minimumFractionDigits: 1, maximumFractionDigits: 1 })

export const int = (n) => nf0.format(n)
export const dec1 = (n) => nf1.format(n)

export function isNumber(v) {
  return typeof v === 'number' && Number.isFinite(v)
}

export function altitude(alt) {
  if (alt === 'ground') return 'En tierra'
  if (!isNumber(alt)) return 'sin dato'
  return `${int(alt)} ft (${int(alt * M_PER_FT)} m)`
}

export function altitudeShort(alt) {
  if (alt === 'ground') return 'tierra'
  if (!isNumber(alt)) return '—'
  return `${int(alt)} ft`
}

export function speed(gs) {
  return isNumber(gs) ? `${int(gs)} kt (${int(gs * KMH_PER_KT)} km/h)` : 'sin dato'
}

export function heading(deg) {
  if (!isNumber(deg)) return 'sin dato'
  return `${String(Math.round(deg) % 360).padStart(3, '0')}°`
}

export function distance(nm) {
  return isNumber(nm) ? `${dec1(nm)} NM (${dec1(nm * 1.852)} km)` : 'sin dato'
}

export function clock(epochSeconds) {
  if (!isNumber(epochSeconds)) return '—'
  return new Date(epochSeconds * 1000).toLocaleTimeString('es-AR')
}

export function identification(ac) {
  return [ac.flight, ac.registration, ac.type].filter(Boolean).join(' · ') || ac.hex?.toUpperCase()
}

// -35.111944 → 35°06'43" S
export function dms(value, isLat) {
  if (!isNumber(value)) return ''
  const hemi = isLat ? (value < 0 ? 'S' : 'N') : value < 0 ? 'W' : 'E'
  let total = Math.round(Math.abs(value) * 3600)
  const d = Math.floor(total / 3600)
  total -= d * 3600
  const m = Math.floor(total / 60)
  const s = total - m * 60
  const pad = (n) => String(n).padStart(2, '0')
  return `${d}°${pad(m)}'${pad(s)}" ${hemi}`
}
