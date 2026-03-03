import { useState, useCallback } from 'react'

const MAX_EVENTS = 500   // cap in-memory event log to prevent memory growth

export function useEventStore() {
  const [events, setEvents] = useState([])

  const addEvent = useCallback((incoming) => {
    // Filter out non-event messages (pings, sweep updates, etc.)
    if (!incoming.category && incoming.type !== 'fusion_verified') return

    // Handle fusion verification updates — mark existing event as verified
    if (incoming.type === 'fusion_verified') {
      setEvents(prev => prev.map(e =>
        e.id === incoming.event_id
          ? { ...e, verified: true, fusion_verified_by: incoming.sensor }
          : e
      ))
      return
    }

    setEvents(prev => {
      // Check for duplicate by id
      const exists = prev.some(e => e.id === incoming.id)
      if (exists) {
        // Update existing event (e.g., confidence change)
        return prev.map(e => e.id === incoming.id ? { ...e, ...incoming } : e)
      }
      // Prepend new event and cap length
      const updated = [incoming, ...prev]
      return updated.length > MAX_EVENTS ? updated.slice(0, MAX_EVENTS) : updated
    })
  }, [])

  const clearEvents = useCallback(() => {
    setEvents([])
  }, [])

  return { events, addEvent, clearEvents }
}
