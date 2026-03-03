import { useState, useCallback, useEffect } from 'react'
import MapContainer from './components/MapContainer'
import EventLog from './components/EventLog'
import StatusBar from './components/StatusBar'
import { useWebSocket } from './hooks/useWebSocket'
import { useEventStore } from './hooks/useEventStore'
import './styles/global.css'

const API_BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

export default function App() {
  const [selectedEvent, setSelectedEvent] = useState(null)
  const { events, addEvent, addEvents } = useEventStore()

  // ── Initial load: hydrate globe from REST on mount ────────────────
  useEffect(() => {
    async function fetchInitialEvents() {
      try {
        const res = await fetch(`${API_BASE}/api/events?limit=200`)
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        const data = await res.json()
        // REST returns newest-first; reverse so addEvents prepends in order
        addEvents(data.reverse())
      } catch (err) {
        console.error('[ARES] Initial event fetch failed:', err)
      }
    }
    fetchInitialEvents()
  }, [])   // eslint-disable-line react-hooks/exhaustive-deps

  // ── WebSocket: handles live events + adsb_sweep + fusion_verified ─
  const handleNewEvent = useCallback((msg) => {
    addEvent(msg)
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
