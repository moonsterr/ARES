/**
 * Color constants for each event category.
 * Used by CesiumJS entity rendering and CSS styling.
 * Colors match the CSS custom properties in global.css.
 */

export const EVENT_COLORS = {
  air_alert:       '#ef4444',   // Red — hostile air
  ground_strike:   '#f97316',   // Orange — kinetic ground
  troop_movement:  '#3b82f6',   // Blue — friendly/movement
  naval_event:     '#06b6d4',   // Cyan — maritime
  explosion:       '#eab308',   // Amber — unverified blast
  casualty_report: '#e879f9',   // Pink — casualty data
  verified:        '#22c55e',   // Green — cross-verified
  conflict:        '#a855f7',   // Purple — conflicting reports
  aircraft:        '#38bdf8',   // Sky blue — ADS-B military aircraft
  unknown:         '#94a3b8',   // Slate — unknown
}

export const EVENT_GLOW_COLORS = {
  air_alert:       'rgba(239, 68, 68, 0.6)',
  ground_strike:   'rgba(249, 115, 22, 0.6)',
  troop_movement:  'rgba(59, 130, 246, 0.6)',
  naval_event:     'rgba(6, 182, 212, 0.6)',
  explosion:       'rgba(234, 179, 8, 0.6)',
  casualty_report: 'rgba(232, 121, 249, 0.6)',
  verified:        'rgba(34, 197, 94, 0.6)',
  conflict:        'rgba(168, 85, 247, 0.6)',
  unknown:         'rgba(148, 163, 184, 0.4)',
}

export const CATEGORY_CSS_VARS = {
  air_alert:       'var(--color-air-alert)',
  ground_strike:   'var(--color-ground-strike)',
  troop_movement:  'var(--color-troop-movement)',
  naval_event:     'var(--color-naval-event)',
  explosion:       'var(--color-explosion)',
  casualty_report: 'var(--color-explosion)',
  verified:        'var(--color-verified)',
  conflict:        'var(--color-conflict)',
  unknown:         'var(--color-text-muted)',
}
