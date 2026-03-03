/**
 * Formatting utilities for timestamps, coordinates, and confidence scores.
 */

/**
 * Format a timestamp as relative time (e.g. "2 min ago", "just now")
 * Falls back to absolute timestamp if parsing fails.
 */
export function formatRelativeTime(timestamp) {
  if (!timestamp) return 'Unknown time'

  try {
    const date   = new Date(timestamp)
    const now    = new Date()
    const diffMs = now - date
    const diffS  = Math.floor(diffMs / 1000)
    const diffM  = Math.floor(diffS / 60)
    const diffH  = Math.floor(diffM / 60)
    const diffD  = Math.floor(diffH / 24)

    if (diffS < 10)  return 'just now'
    if (diffS < 60)  return `${diffS}s ago`
    if (diffM < 60)  return `${diffM}m ago`
    if (diffH < 24)  return `${diffH}h ago`
    if (diffD < 7)   return `${diffD}d ago`

    return date.toLocaleDateString('en-US', {
      month: 'short',
      day:   'numeric',
      year:  '2-digit',
    })
  } catch {
    return String(timestamp)
  }
}

/**
 * Format a timestamp as absolute UTC time string
 */
export function formatAbsoluteTime(timestamp) {
  if (!timestamp) return '—'
  try {
    return new Date(timestamp).toISOString().replace('T', ' ').slice(0, 19) + ' UTC'
  } catch {
    return String(timestamp)
  }
}

/**
 * Format coordinates to human-readable string
 */
export function formatCoords(lat, lon) {
  if (lat == null || lon == null) return 'Unknown location'
  const latDir = lat >= 0 ? 'N' : 'S'
  const lonDir = lon >= 0 ? 'E' : 'W'
  return `${Math.abs(lat).toFixed(4)}°${latDir}  ${Math.abs(lon).toFixed(4)}°${lonDir}`
}

/**
 * Format confidence score as percentage string
 */
export function formatConfidence(value) {
  if (value == null) return '—'
  return `${(value * 100).toFixed(1)}%`
}

/**
 * Format Bel/Pl interval as string
 */
export function formatBelPl(bel, pl) {
  if (bel == null || pl == null) return '—'
  return `[${(bel * 100).toFixed(0)}%, ${(pl * 100).toFixed(0)}%]`
}

/**
 * Truncate text to maxLength with ellipsis
 */
export function truncateText(text, maxLength = 120) {
  if (!text) return ''
  if (text.length <= maxLength) return text
  return text.slice(0, maxLength - 3) + '...'
}
