/**
 * ACLED service — fetches Armed Conflict Location & Event Data from the ARES backend.
 * Data is collected by Agent CHARLIE-A (backend/agents/acled_fetcher.py).
 */
const API_BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

/**
 * Fetch recent ACLED-sourced conflict events.
 * @param {object} options
 * @param {number} [options.limit=100]   - Max events to return (1–500)
 * @param {string} [options.category]    - Filter by EventCategory (e.g. 'explosion')
 * @returns {Promise<Array>} Array of conflict event objects
 */
export async function fetchAcledEvents({ limit = 100, category = null } = {}) {
  try {
    const params = new URLSearchParams({ limit })
    if (category) params.set('category', category)

    const res = await fetch(`${API_BASE}/api/acled-events?${params}`)
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    return await res.json()
  } catch (err) {
    console.error('[ACLED] Fetch failed:', err)
    return []
  }
}
