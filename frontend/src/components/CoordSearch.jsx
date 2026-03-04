import { useState, useRef } from 'react'

/**
 * CoordSearch — floating coordinate input overlay on the globe.
 *
 * Props:
 *   onFlyTo(lat, lon) — called when the user submits valid coordinates.
 *
 * Accepts:
 *   • Decimal degrees:  "33.8938, 35.5018"
 *   • DMS shorthand:    "33°53'37\"N 35°30'6\"E"  (parsed to decimal)
 *   • Lat then lon, or lon then lat if lon is clearly > 90 → auto-swap
 */
export default function CoordSearch({ onFlyTo }) {
  const [open,    setOpen]    = useState(false)
  const [input,   setInput]   = useState('')
  const [error,   setError]   = useState('')
  const inputRef = useRef(null)

  function toggle() {
    setOpen(o => {
      if (!o) setTimeout(() => inputRef.current?.focus(), 50)
      return !o
    })
    setError('')
    setInput('')
  }

  function parseDMS(str) {
    // e.g. 33°53'37"N  or  33d53m37sN
    const m = str.trim().match(
      /^(\d+)[°d]\s*(\d+)[''m]\s*([\d.]+)[""s]?\s*([NSEW]?)$/i
    )
    if (!m) return null
    const deg = parseFloat(m[1])
    const min = parseFloat(m[2])
    const sec = parseFloat(m[3])
    const dir = m[4].toUpperCase()
    let decimal = deg + min / 60 + sec / 3600
    if (dir === 'S' || dir === 'W') decimal = -decimal
    return decimal
  }

  function parseCoords(raw) {
    // Split on comma, semicolon, or whitespace-only separator
    const parts = raw.trim().split(/[,;]\s*|\s{2,}/).map(s => s.trim()).filter(Boolean)

    if (parts.length < 2) return null

    // Try decimal first
    let a = parseFloat(parts[0])
    let b = parseFloat(parts[1])

    // If plain floats didn't work, try DMS
    if (isNaN(a)) a = parseDMS(parts[0])
    if (isNaN(b)) b = parseDMS(parts[1])

    if (a == null || b == null || isNaN(a) || isNaN(b)) return null

    // Auto-detect if user entered lon,lat instead of lat,lon
    // (lon must be in [-180,180], lat in [-90,90])
    let lat = a, lon = b
    if (Math.abs(a) > 90 && Math.abs(b) <= 90) {
      // looks like lon,lat — swap
      lat = b; lon = a
    }

    if (lat < -90 || lat > 90)   return null
    if (lon < -180 || lon > 180) return null

    return { lat, lon }
  }

  function handleSubmit(e) {
    e.preventDefault()
    setError('')

    const result = parseCoords(input)
    if (!result) {
      setError('Invalid coordinates. Try: 33.89, 35.50')
      return
    }

    onFlyTo(result.lat, result.lon)
    setOpen(false)
    setInput('')
  }

  function handleKey(e) {
    if (e.key === 'Escape') {
      setOpen(false)
      setError('')
    }
  }

  return (
    <div className="coord-search" onKeyDown={handleKey}>
      {/* Toggle button */}
      <button
        className="coord-search__btn"
        onClick={toggle}
        title="Fly to coordinates"
        aria-label="Fly to coordinates"
      >
        ⌖
      </button>

      {/* Input panel */}
      {open && (
        <form className="coord-search__panel" onSubmit={handleSubmit}>
          <div className="coord-search__label">FLY TO COORDINATES</div>
          <div className="coord-search__row">
            <input
              ref={inputRef}
              className={`coord-search__input${error ? ' coord-search__input--error' : ''}`}
              type="text"
              placeholder="lat, lon  —  e.g. 33.89, 35.50"
              value={input}
              onChange={e => { setInput(e.target.value); setError('') }}
              spellCheck={false}
              autoComplete="off"
            />
            <button className="coord-search__go" type="submit">GO</button>
          </div>
          {error && <div className="coord-search__error">{error}</div>}
          <div className="coord-search__hint">
            Decimal · DMS · lon,lat auto-detected
          </div>
        </form>
      )}
    </div>
  )
}
