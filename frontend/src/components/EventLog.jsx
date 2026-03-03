import EventCard from './EventCard'
import '../styles/sidebar.css'

export default function EventLog({ events, selectedEvent, onEventClick }) {
  // Events are shown newest first
  const sortedEvents = [...events].reverse()

  return (
    <div className="event-log">
      <div className="event-log__header">
        <h2 className="event-log__title">INTELLIGENCE FEED</h2>
        <span className="event-log__count">{events.length} EVENTS</span>
      </div>

      {sortedEvents.length === 0 ? (
        <div className="event-log__empty">
          <p>Awaiting signal...</p>
          <p className="event-log__empty-sub">WebSocket connected — monitoring active sources</p>
        </div>
      ) : (
        <div className="event-log__list">
          {sortedEvents.map(event => (
            <EventCard
              key={event.id}
              event={event}
              isSelected={selectedEvent?.id === event.id}
              onClick={onEventClick}
            />
          ))}
        </div>
      )}
    </div>
  )
}
