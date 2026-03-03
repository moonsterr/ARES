import { useState, useCallback } from 'react'

const MAX_EVENTS = 500   // cap in-memory event log to prevent memory growth

export function useEventStore() {
  const [events, setEvents] = useState([])

  const addEvent = useCallback((incoming) => {
    // ── ADS-B sweep: unpack aircraft array into individual pseudo-events ──
    if (incoming.type === 'adsb_sweep') {
      const aircraft = incoming.aircraft ?? []
      setEvents(prev => {
        let next = [...prev]
        for (const ac of aircraft) {
          const id = `adsb-${ac.icao_hex}`
          const pseudoEvent = {
            id,
            category:      'aircraft',
            lat:           ac.lat,
            lon:           ac.lon,
            location_name: ac.callsign || ac.icao_hex,
            confidence:    1.0,
            sources:       ['adsb.lol'],
            // extra ADS-B fields for the info card
            icao_hex:      ac.icao_hex,
            callsign:      ac.callsign,
            altitude_ft:   ac.altitude,
            heading:       ac.heading,
            speed_kts:     ac.speed_kts,
            ac_type:       ac.type,
            desc:          ac.desc,
            created_at:    new Date().toISOString(),
          }
          const idx = next.findIndex(e => e.id === id)
          if (idx !== -1) {
            next[idx] = { ...next[idx], ...pseudoEvent }
          } else {
            next = [pseudoEvent, ...next]
          }
        }
        return next.length > MAX_EVENTS ? next.slice(0, MAX_EVENTS) : next
      })
      return
    }

    // ── Fusion verification: mark existing event as satellite-confirmed ──
    if (incoming.type === 'fusion_verified') {
      setEvents(prev => prev.map(e =>
        e.id === incoming.event_id
          ? { ...e, verified: true, fusion_verified_by: incoming.sensor }
          : e
      ))
      return
    }

    // ── Ping / unknown system messages: ignore ──
    if (!incoming.category) return

    // ── Standard conflict event ──
    setEvents(prev => {
      const exists = prev.some(e => e.id === incoming.id)
      if (exists) {
        return prev.map(e => e.id === incoming.id ? { ...e, ...incoming } : e)
      }
      const updated = [incoming, ...prev]
      return updated.length > MAX_EVENTS ? updated.slice(0, MAX_EVENTS) : updated
    })
  }, [])

  // Bulk-load events (used for initial REST hydration)
  const addEvents = useCallback((list) => {
    setEvents(prev => {
      const existingIds = new Set(prev.map(e => e.id))
      const fresh = list.filter(e => !existingIds.has(e.id))
      const merged = [...fresh, ...prev]
      return merged.length > MAX_EVENTS ? merged.slice(0, MAX_EVENTS) : merged
    })
  }, [])

  const clearEvents = useCallback(() => {
    setEvents([])
  }, [])

  return { events, addEvent, addEvents, clearEvents }
}
