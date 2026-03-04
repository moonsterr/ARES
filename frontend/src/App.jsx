import { useState, useCallback, useEffect } from 'react'
import DeckGLMap from './components/DeckGLMap'
import EventLog from './components/EventLog'
import StatusBar from './components/StatusBar'
import { useWebSocket } from './hooks/useWebSocket'
import { useEventStore } from './hooks/useEventStore'
import { fetchInfrastructure } from './services/infrastructure'
import { LAYER_CONFIG, LAYER_ORDER } from './config/mapLayers'
import './styles/global.css'

const API_BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

export default function App() {
  const [selectedEvent, setSelectedEvent] = useState(null)
  const [showLayerPanel, setShowLayerPanel] = useState(false)
  const { 
    events, 
    addEvent, 
    addEvents,
    layerVisibility,
    toggleLayer,
    infrastructure,
    setInfrastructureData,
  } = useEventStore()

  // Filter aircraft and vessels from events for DeckGLMap
  const aircraft = events.filter(e => e.category === 'aircraft')
  const vessels = events.filter(e => e.category === 'vessel')
  const hotspots = events.filter(e => e.category === 'hotspot')
  const conflictEvents = events.filter(e => e.category && e.category !== 'aircraft' && e.category !== 'vessel')

  // ── Initial load: hydrate events + infrastructure from REST ────────────
  useEffect(() => {
    async function fetchInitialData() {
      try {
        const [eventsRes, infraRes] = await Promise.all([
          fetch(`${API_BASE}/api/events?limit=200`),
          fetchInfrastructure(),
        ])
        
        if (eventsRes.ok) {
          const data = await eventsRes.json()
          addEvents(data.reverse())
        }
        
        setInfrastructureData(infraRes)
      } catch (err) {
        console.error('[ARES] Initial data fetch failed:', err)
      }
    }
    fetchInitialData()
  }, [])

  // ── WebSocket: handles live events + adsb_sweep + fusion_verified ─
  const handleNewEvent = useCallback((msg) => {
    addEvent(msg)
  }, [addEvent])

  const { status } = useWebSocket('/ws/events', handleNewEvent)

  const getLayerVisibility = useCallback((layerId) => {
    if (layerId in layerVisibility) return layerVisibility[layerId]
    return LAYER_CONFIG[layerId]?.defaultVisibility ?? true
  }, [layerVisibility])

  return (
    <div className="ares-root">
      <StatusBar wsStatus={status} eventCount={events.length} />
      <div className="ares-layout">
        <main className="ares-globe-container">
          <DeckGLMap
            events={conflictEvents}
            aircraft={aircraft}
            vessels={vessels}
            hotspots={hotspots}
            infrastructure={infrastructure}
            layerVisibility={layerVisibility}
            onEntitySelect={setSelectedEvent}
          />
          <button
            className="layer-toggle-btn"
            onClick={() => setShowLayerPanel(!showLayerPanel)}
            style={{
              position: 'absolute',
              top: '16px',
              right: '16px',
              zIndex: 100,
              padding: '8px 12px',
              background: 'rgba(15, 23, 42, 0.9)',
              border: '1px solid rgba(148, 163, 184, 0.3)',
              borderRadius: '6px',
              color: '#f1f5f9',
              cursor: 'pointer',
              fontSize: '12px',
              fontFamily: 'var(--font-mono, monospace)',
            }}
          >
            {showLayerPanel ? '✕ Layers' : '☰ Layers'}
          </button>
          
          {showLayerPanel && (
            <div
              className="layer-panel"
              style={{
                position: 'absolute',
                top: '56px',
                right: '16px',
                zIndex: 100,
                background: 'rgba(15, 23, 42, 0.95)',
                border: '1px solid rgba(148, 163, 184, 0.3)',
                borderRadius: '8px',
                padding: '12px',
                minWidth: '200px',
                maxHeight: '70vh',
                overflowY: 'auto',
              }}
            >
              <div style={{ 
                color: '#94a3b8', 
                fontSize: '10px', 
                textTransform: 'uppercase', 
                marginBottom: '8px',
                fontFamily: 'var(--font-mono, monospace)',
              }}>
                Map Layers
              </div>
              {LAYER_ORDER.map(layerId => {
                const config = LAYER_CONFIG[layerId]
                if (!config) return null
                const isVisible = getLayerVisibility(layerId)
                return (
                  <label
                    key={layerId}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '8px',
                      padding: '6px 0',
                      cursor: 'pointer',
                      borderBottom: '1px solid rgba(148, 163, 184, 0.1)',
                      fontSize: '12px',
                      color: isVisible ? '#f1f5f9' : '#64748b',
                      fontFamily: 'var(--font-mono, monospace)',
                    }}
                  >
                    <input
                      type="checkbox"
                      checked={isVisible}
                      onChange={() => toggleLayer(layerId)}
                      style={{ accentColor: '#3b82f6' }}
                    />
                    <span style={{ 
                      width: '8px', 
                      height: '8px', 
                      borderRadius: '50%',
                      background: config.color || '#94a3b8',
                      display: 'inline-block',
                    }} />
                    {config.label}
                  </label>
                )
              })}
            </div>
          )}
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
