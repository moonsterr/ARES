// Appears in sidebar AND as an overlay at high globe zoom.
// Uses Vanilla CSS glassmorphism — no component library.

import ConfidenceMeter from './ConfidenceMeter'
import { formatRelativeTime } from '../lib/formatters'
import '../styles/cards.css'

const CATEGORY_LABELS = {
  air_alert:       'AIR ALERT',
  ground_strike:   'GROUND STRIKE',
  troop_movement:  'TROOP MOVEMENT',
  naval_event:     'NAVAL EVENT',
  explosion:       'EXPLOSION',
  casualty_report: 'CASUALTY REPORT',
  unknown:         'INTELLIGENCE',
}

export default function EventCard({ event, isSelected, onClick }) {
  const categoryClass = `event-card--${event.category}`

  return (
    <article
      className={`event-card ${categoryClass} ${isSelected ? 'event-card--selected' : ''}`}
      onClick={() => onClick(event)}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => e.key === 'Enter' && onClick(event)}
    >
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
      </header>

      <div className="event-card__location">
        <span className="event-card__location-name">
          {event.location_name ?? 'Location undetermined'}
        </span>
        {event.lat && event.lon && (
          <span className="event-card__coords">
            {Number(event.lat).toFixed(4)}°N {Number(event.lon).toFixed(4)}°E
          </span>
        )}
      </div>

      <p className="event-card__translation">
        {event.translation || event.raw_text}
      </p>

      <footer className="event-card__footer">
        <ConfidenceMeter
          bel={event.bel ?? 0}
          pl={event.pl ?? 1}
          conflictK={event.conflict_k ?? 0}
        />
        <span className="event-card__source">
          {event.source}
        </span>
      </footer>
    </article>
  )
}
