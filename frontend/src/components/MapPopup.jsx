import React from 'react'

const CATEGORY_LABELS = {
  air_alert: 'Air Alert',
  ground_strike: 'Ground Strike',
  troop_movement: 'Troop Movement',
  naval_event: 'Naval Event',
  explosion: 'Explosion',
  casualty_report: 'Casualty Report',
  aircraft: 'Military Aircraft',
  vessel: 'Naval Vessel',
  unknown: 'Unknown',
}

function formatRelativeTime(timestamp) {
  if (!timestamp) return ''
  const now = new Date()
  const then = new Date(timestamp)
  const diffMs = now - then
  const diffMins = Math.floor(diffMs / 60000)
  const diffHours = Math.floor(diffMins / 60)
  const diffDays = Math.floor(diffHours / 24)

  if (diffMins < 1) return 'just now'
  if (diffMins < 60) return `${diffMins}m ago`
  if (diffHours < 24) return `${diffHours}h ago`
  if (diffDays < 7) return `${diffDays}d ago`
  return then.toLocaleDateString()
}

function formatCoords(lat, lon) {
  if (lat == null || lon == null) return ''
  const latDir = lat >= 0 ? 'N' : 'S'
  const lonDir = lon >= 0 ? 'E' : 'W'
  return `${Math.abs(lat).toFixed(4)}°${latDir} ${Math.abs(lon).toFixed(4)}°${lonDir}`
}

export default function MapPopup({ object, onClose }) {
  if (!object) return null

  const isEvent = object.category && object.category !== 'aircraft' && object.category !== 'vessel'
  const isAircraft = object.category === 'aircraft' || object.icao_hex
  const isVessel = object.category === 'vessel' || object.mmsi
  const isInfrastructure = object.type || object.properties

  return (
    <div
      style={{
        position: 'absolute',
        top: '50%',
        left: '50%',
        transform: 'translate(-50%, -50%)',
        background: 'rgba(15, 23, 42, 0.95)',
        border: '1px solid rgba(148, 163, 184, 0.3)',
        borderRadius: '8px',
        padding: '16px',
        minWidth: '280px',
        maxWidth: '360px',
        zIndex: 1000,
        color: '#f1f5f9',
        fontFamily: 'var(--font-mono, monospace)',
        boxShadow: '0 4px 24px rgba(0, 0, 0, 0.5)',
      }}
    >
      <button
        onClick={onClose}
        style={{
          position: 'absolute',
          top: '8px',
          right: '8px',
          background: 'transparent',
          border: 'none',
          color: '#94a3b8',
          cursor: 'pointer',
          fontSize: '18px',
          lineHeight: 1,
        }}
      >
        ×
      </button>

      {isEvent && (
        <>
          <div style={{ marginBottom: '12px' }}>
            <span
              style={{
                display: 'inline-block',
                padding: '4px 8px',
                borderRadius: '4px',
                fontSize: '11px',
                fontWeight: 600,
                textTransform: 'uppercase',
                background: object.verified ? '#22c55e' : 
                  object.conflict_k > 0.4 ? '#a855f7' : 
                  object.category === 'air_alert' ? '#ef4444' :
                  object.category === 'ground_strike' ? '#f97316' :
                  object.category === 'troop_movement' ? '#3b82f6' :
                  object.category === 'naval_event' ? '#06b6d4' :
                  object.category === 'explosion' ? '#eab308' : '#94a3b8',
                color: '#fff',
              }}
            >
              {object.verified ? 'VERIFIED' : CATEGORY_LABELS[object.category] || object.category}
            </span>
            {object.verified && (
              <span style={{ marginLeft: '8px', color: '#22c55e', fontSize: '11px' }}>
                ★ SATELLITE CONFIRMED
              </span>
            )}
          </div>

          <div style={{ fontSize: '14px', marginBottom: '8px', fontWeight: 500 }}>
            {object.location_name || 'Unknown Location'}
          </div>

          <div style={{ fontSize: '12px', color: '#94a3b8', marginBottom: '12px' }}>
            {formatCoords(object.lat, object.lon)}
          </div>

          {object.translation && (
            <div style={{ 
              fontSize: '12px', 
              color: '#cbd5e1', 
              marginBottom: '12px',
              padding: '8px',
              background: 'rgba(30, 41, 59, 0.5)',
              borderRadius: '4px',
              borderLeft: '3px solid #3b82f6',
            }}>
              {object.translation}
            </div>
          )}

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', fontSize: '11px' }}>
            <div>
              <span style={{ color: '#64748b' }}>Confidence: </span>
              <span style={{ color: object.confidence > 0.7 ? '#22c55e' : object.confidence > 0.4 ? '#eab308' : '#ef4444' }}>
                {object.confidence != null ? `${(object.confidence * 100).toFixed(0)}%` : 'N/A'}
              </span>
            </div>
            {object.conflict_k != null && (
              <div>
                <span style={{ color: '#64748b' }}>Conflict K: </span>
                <span style={{ color: object.conflict_k > 0.4 ? '#a855f7' : '#94a3b8' }}>
                  {object.conflict_k.toFixed(2)}
                </span>
              </div>
            )}
          </div>

          <div style={{ marginTop: '12px', paddingTop: '12px', borderTop: '1px solid rgba(148, 163, 184, 0.2)', fontSize: '11px', color: '#64748b' }}>
            {object.created_at && <div>Time: {formatRelativeTime(object.created_at)}</div>}
            {object.source && <div>Source: {object.source}</div>}
          </div>
        </>
      )}

      {isAircraft && (
        <>
          <div style={{ marginBottom: '12px', fontSize: '16px', fontWeight: 600 }}>
            {object.callsign || object.icao_hex || 'Aircraft'}
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', fontSize: '12px' }}>
            <div>
              <span style={{ color: '#64748b' }}>ICAO: </span>
              <span style={{ color: '#f1f5f9' }}>{object.icao_hex || 'N/A'}</span>
            </div>
            <div>
              <span style={{ color: '#64748b' }}>Type: </span>
              <span style={{ color: '#f1f5f9' }}>{object.ac_type || object.type || 'N/A'}</span>
            </div>
            <div>
              <span style={{ color: '#64748b' }}>Altitude: </span>
              <span style={{ color: '#f1f5f9' }}>{object.altitude_ft ? `${object.altitude_ft} ft` : 'N/A'}</span>
            </div>
            <div>
              <span style={{ color: '#64748b' }}>Speed: </span>
              <span style={{ color: '#f1f5f9' }}>{object.speed_kts ? `${object.speed_kts} kts` : 'N/A'}</span>
            </div>
            <div>
              <span style={{ color: '#64748b' }}>Heading: </span>
              <span style={{ color: '#f1f5f9' }}>{object.heading ? `${object.heading}°` : 'N/A'}</span>
            </div>
            <div>
              <span style={{ color: '#64748b' }}>Registration: </span>
              <span style={{ color: '#f1f5f9' }}>{object.reg || object.registration || 'N/A'}</span>
            </div>
          </div>

          <div style={{ marginTop: '12px', fontSize: '11px', color: '#64748b' }}>
            {formatCoords(object.lat, object.lon)}
          </div>
        </>
      )}

      {isVessel && (
        <>
          <div style={{ marginBottom: '12px', fontSize: '16px', fontWeight: 600 }}>
            {object.name || object.mmsi || 'Vessel'}
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', fontSize: '12px' }}>
            <div>
              <span style={{ color: '#64748b' }}>MMSI: </span>
              <span style={{ color: '#f1f5f9' }}>{object.mmsi || 'N/A'}</span>
            </div>
            <div>
              <span style={{ color: '#64748b' }}>Type: </span>
              <span style={{ color: '#f1f5f9' }}>{object.vessel_type || object.type || 'N/A'}</span>
            </div>
            <div>
              <span style={{ color: '#64748b' }}>Flag: </span>
              <span style={{ color: '#f1f5f9' }}>{object.flag || 'N/A'}</span>
            </div>
            <div>
              <span style={{ color: '#64748b' }}>Speed: </span>
              <span style={{ color: '#f1f5f9' }}>{object.speed_kts ? `${object.speed_kts} kts` : 'N/A'}</span>
            </div>
          </div>

          <div style={{ marginTop: '12px', fontSize: '11px', color: '#64748b' }}>
            {formatCoords(object.lat, object.lon)}
          </div>
        </>
      )}

      {isInfrastructure && !isEvent && !isAircraft && !isVessel && (
        <>
          <div style={{ marginBottom: '12px', fontSize: '16px', fontWeight: 600 }}>
            {object.name || object.properties?.name || object.properties?.title || 'Infrastructure'}
          </div>

          <div style={{ fontSize: '12px', color: '#cbd5e1' }}>
            {object.properties?.description || object.type || 'Infrastructure data'}
          </div>

          <div style={{ marginTop: '12px', fontSize: '11px', color: '#64748b' }}>
            {formatCoords(object.lat || object.properties?.lat, object.lon || object.properties?.lon)}
          </div>
        </>
      )}
    </div>
  )
}
