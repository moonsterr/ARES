import { useState, useCallback } from 'react'
import MapContainer from './components/MapContainer'
import EventLog from './components/EventLog'
import StatusBar from './components/StatusBar'
import { useWebSocket } from './hooks/useWebSocket'
import { useEventStore } from './hooks/useEventStore'
import './styles/global.css'

export default function App() {
  const [selectedEvent, setSelectedEvent] = useState(null)
  const { events, addEvent } = useEventStore()

  // onEvent is called by useWebSocket on every incoming message
  const handleNewEvent = useCallback((event) => {
    addEvent(event)
  }, [addEvent])

  const { status } = useWebSocket('/ws/events', handleNewEvent)

  return (
    <div className="ares-root">
      <StatusBar wsStatus={status} eventCount={events.length} />
      <div className="ares-layout">
        <main className="ares-globe-container">
          <MapContainer
            events={events}
            onEntitySelect={setSelectedEvent}
          />
        </main>
        <aside className="ares-sidebar">
          <EventLog
            events={events}
            selectedEvent={selectedEvent}
            onEventClick={setSelectedEvent}
          />
        </aside>
      </div>
    </div>
  )
}
