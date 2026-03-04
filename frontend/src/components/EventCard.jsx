// Appears in sidebar AND as an overlay at high globe zoom.
// Uses Vanilla CSS glassmorphism — no component library.

import { useState } from 'react'
import ConfidenceMeter from './ConfidenceMeter'
import { formatRelativeTime, formatAbsoluteTime, formatCoords } from '../lib/formatters'
import '../styles/cards.css'

const CATEGORY_LABELS = {
  air_alert:       'AIR ALERT',
  ground_strike:   'GROUND STRIKE',
  troop_movement:  'TROOP MOVEMENT',
  naval_event:     'NAVAL EVENT',
  explosion:       'EXPLOSION',
  casualty_report: 'CASUALTY REPORT',
  kinetic:         'KINETIC',
  unknown:         'INTELLIGENCE',
}

export default function EventCard({ event, isSelected, onClick }) {
  const [expanded, setExpanded] = useState(false)
  const categoryClass = `event-card--${event.category}`

  // Body text lives in `translation` (bravo_news summary) or falls back to raw_text
  const headline    = event.raw_text ?? ''
  const description = event.translation ?? ''
  const hasDescription = description && description !== headline
  const canExpand   = hasDescription || (event.sources?.length > 0)

  function handleCardClick() {
    onClick(event)
  }

  function handleChevronClick(e) {
    e.stopPropagation()
    setExpanded(prev => !prev)
  }

  // Safe hostname extraction from a URL string
  function hostnameOf(url) {
    try { return new URL(url).hostname } catch { return url }
  }

  return (
    <article
      className={`event-card ${categoryClass} ${isSelected ? 'event-card--selected' : ''} ${expanded ? 'event-card--expanded' : ''}`}
      onClick={handleCardClick}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => e.key === 'Enter' && handleCardClick()}
    >
      {/* ── Header ───────────────────────────────────────────────── */}
      <header className="event-card__header">
        <span className={`event-card__category-badge badge--${event.category}`}>
          {CATEGORY_LABELS[event.category] ?? 'INTELLIGENCE'}
        </span>
        {event.verified && (
          <span className="event-card__verified-badge">VERIFIED</span>
        )}
        <time className="event-card__time">
          {formatRelativeTime(event.created_at)}
        </time>
        {canExpand && (
          <button
            className={`event-card__chevron ${expanded ? 'event-card__chevron--open' : ''}`}
            onClick={handleChevronClick}
            aria-label={expanded ? 'Collapse details' : 'Expand details'}
          >
            ▾
          </button>
        )}
      </header>

      {/* ── Location ─────────────────────────────────────────────── */}
      <div className="event-card__location">
        <span className="event-card__location-name">
          {event.location_name ?? 'Location undetermined'}
        </span>
        {event.lat != null && event.lon != null && (
          <span className="event-card__coords">
            {formatCoords(event.lat, event.lon)}
          </span>
        )}
      </div>

      {/* ── Headline — clamped to 2 lines when collapsed ─────────── */}
      <p className={`event-card__translation ${expanded ? 'event-card__translation--full' : ''}`}>
        {headline}
      </p>

      {/* ── Expanded details panel ───────────────────────────────── */}
      <div className={`event-card__details ${expanded ? 'event-card__details--open' : ''}`}>
        {hasDescription && (
          <div className="event-card__description-block">
            <span className="event-card__details-label">SUMMARY</span>
            <p className="event-card__description">{description}</p>
          </div>
        )}

        <div className="event-card__meta-grid">
          <div className="event-card__meta-item">
            <span className="event-card__details-label">TIME</span>
            <span className="event-card__meta-value">
              {formatAbsoluteTime(event.created_at)}
            </span>
          </div>
          {event.confidence != null && (
            <div className="event-card__meta-item">
              <span className="event-card__details-label">CONF</span>
              <span className="event-card__meta-value">
                {(event.confidence * 100).toFixed(0)}%
              </span>
            </div>
          )}
          {event.fusion_status && event.fusion_status !== 'SINGLE_SOURCE' && (
            <div className="event-card__meta-item">
              <span className="event-card__details-label">FUSION</span>
              <span className="event-card__meta-value">{event.fusion_status}</span>
            </div>
          )}
        </div>

        {event.sources?.length > 0 && (
          <div className="event-card__sources">
            <span className="event-card__details-label">SOURCE</span>
            {event.sources.map((src, i) => (
              <a
                key={i}
                href={src}
                target="_blank"
                rel="noopener noreferrer"
                className="event-card__source-link"
                onClick={e => e.stopPropagation()}
                title={src}
              >
                {hostnameOf(src)}
              </a>
            ))}
          </div>
        )}
      </div>

      {/* ── Footer ───────────────────────────────────────────────── */}
      <footer className="event-card__footer">
        <ConfidenceMeter
          bel={event.bel ?? 0}
          pl={event.pl ?? 1}
          conflictK={event.conflict_k ?? 0}
        />
        <span className="event-card__source">
          {event.source ?? (event.sources?.[0] ? hostnameOf(event.sources[0]) : '')}
        </span>
      </footer>
    </article>
  )
}
