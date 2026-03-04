/**
 * MapLegend — displays colour/symbol key for map layers.
 * Shows event categories (dots) and infrastructure layers (lines/icons).
 * Styled to match the ARES dark-theme aesthetic.
 */
import { useState } from 'react'

// ── Event category colour definitions (must match mapLayers.js) ───────
const EVENT_CATEGORIES = [
  { label: 'Air Strike / Alert',   color: '#ef4444' },
  { label: 'Ground Strike / Clash', color: '#f97316' },
  { label: 'Troop Movement',       color: '#3b82f6' },
  { label: 'Naval Event',          color: '#06b6d4' },
  { label: 'Explosion',            color: '#eab308' },
  { label: 'Casualty Report',      color: '#e879f9' },
  { label: 'Verified (FIRMS)',     color: '#22c55e' },
  { label: 'High Conflict-K',      color: '#a855f7' },
  { label: 'Unknown / Low-conf',   color: '#94a3b8' },
]

// ── Infrastructure layer symbols ──────────────────────────────────────
const INFRA_LAYERS = [
  { label: 'Military Bases',   symbol: 'square', color: '#ef4444' },
  { label: 'Ports',            symbol: 'square', color: '#22c55e' },
  { label: 'Nuclear Sites',    symbol: 'square', color: '#facc15' },
  { label: 'Submarine Cables', symbol: 'line',   color: '#3b82f6' },
  { label: 'Pipelines (oil)',  symbol: 'line',   color: '#ef4444' },
  { label: 'Pipelines (gas)',  symbol: 'line',   color: '#22c55e' },
]

// ── Source labels ─────────────────────────────────────────────────────
const SOURCES = [
  { label: 'ACLED',    color: '#fb923c', description: 'Armed Conflict Location & Event Data' },
  { label: 'UCDP',    color: '#a78bfa', description: 'Uppsala Conflict Data Program' },
  { label: 'GDELT',   color: '#38bdf8', description: 'Global Event Language & Tone database' },
  { label: 'RSS',     color: '#4ade80', description: '170+ curated news feeds' },
  { label: 'NGA',     color: '#fbbf24', description: 'NGA NAVAREA maritime warnings' },
  { label: 'FIRMS',   color: '#f97316', description: 'NASA thermal hotspot sensor' },
]

// ── Small symbol components ───────────────────────────────────────────

function DotSymbol({ color }) {
  return (
    <span
      style={{
        display:      'inline-block',
        width:        10,
        height:       10,
        borderRadius: '50%',
        backgroundColor: color,
        boxShadow:    `0 0 4px ${color}`,
        flexShrink:   0,
      }}
    />
  )
}

function LineSymbol({ color }) {
  return (
    <span
      style={{
        display:         'inline-block',
        width:           18,
        height:          3,
        backgroundColor: color,
        borderRadius:    2,
        flexShrink:      0,
        alignSelf:       'center',
      }}
    />
  )
}

function SquareSymbol({ color }) {
  return (
    <span
      style={{
        display:         'inline-block',
        width:           10,
        height:          10,
        backgroundColor: color,
        borderRadius:    2,
        flexShrink:      0,
      }}
    />
  )
}

// ── Section heading ───────────────────────────────────────────────────

function SectionTitle({ children }) {
  return (
    <div style={{
      fontSize:      9,
      letterSpacing: '0.12em',
      color:         '#64748b',
      textTransform: 'uppercase',
      marginBottom:  4,
      marginTop:     8,
      fontWeight:    600,
    }}>
      {children}
    </div>
  )
}

// ── Legend row ────────────────────────────────────────────────────────

function LegendRow({ symbol, color, label, description }) {
  return (
    <div
      title={description}
      style={{
        display:    'flex',
        alignItems: 'center',
        gap:        6,
        marginBottom: 3,
        cursor:     description ? 'help' : 'default',
      }}
    >
      {symbol === 'line'   && <LineSymbol   color={color} />}
      {symbol === 'square' && <SquareSymbol color={color} />}
      {(!symbol || symbol === 'dot') && <DotSymbol color={color} />}
      <span style={{ fontSize: 10, color: '#cbd5e1', lineHeight: 1.3 }}>{label}</span>
    </div>
  )
}

// ── Main component ────────────────────────────────────────────────────

export default function MapLegend() {
  const [collapsed, setCollapsed] = useState(false)

  return (
    <div
      style={{
        position:        'absolute',
        bottom:          24,
        left:            12,
        background:      'rgba(15, 23, 42, 0.88)',
        border:          '1px solid rgba(51, 65, 85, 0.8)',
        borderRadius:    6,
        padding:         collapsed ? '6px 10px' : '10px 12px',
        minWidth:        160,
        backdropFilter:  'blur(8px)',
        zIndex:          1000,
        fontFamily:      '"JetBrains Mono", "Fira Code", monospace',
        userSelect:      'none',
        boxShadow:       '0 4px 20px rgba(0,0,0,0.5)',
        transition:      'padding 0.15s',
      }}
    >
      {/* Header */}
      <div
        onClick={() => setCollapsed(c => !c)}
        style={{
          display:     'flex',
          justifyContent: 'space-between',
          alignItems:  'center',
          cursor:      'pointer',
          fontSize:    10,
          color:       '#94a3b8',
          letterSpacing: '0.1em',
          textTransform: 'uppercase',
          fontWeight:  700,
        }}
      >
        <span>Legend</span>
        <span style={{ fontSize: 12, lineHeight: 1 }}>{collapsed ? '▲' : '▼'}</span>
      </div>

      {!collapsed && (
        <>
          {/* Event categories */}
          <SectionTitle>Event Categories</SectionTitle>
          {EVENT_CATEGORIES.map(({ label, color }) => (
            <LegendRow key={label} color={color} label={label} />
          ))}

          {/* Infrastructure */}
          <SectionTitle>Infrastructure</SectionTitle>
          {INFRA_LAYERS.map(({ label, symbol, color }) => (
            <LegendRow key={label} symbol={symbol} color={color} label={label} />
          ))}

          {/* Data sources */}
          <SectionTitle>Data Sources</SectionTitle>
          {SOURCES.map(({ label, color, description }) => (
            <LegendRow key={label} color={color} label={label} description={description} />
          ))}
        </>
      )}
    </div>
  )
}
