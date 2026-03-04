/**
 * UCDP service — fetches Uppsala Conflict Data Program events from the ARES backend.
 * Data is collected by Agent CHARLIE-B (backend/agents/ucdp_fetcher.py).
 * Also exposes NGA NAVAREA maritime warnings via the same module for convenience.
 */
const API_BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

/**
 * Fetch recent UCDP-sourced conflict events.
 * @param {object} options
 * @param {number} [options.limit=100]  - Max events to return (1–500)
 * @param {string} [options.category]   - Filter by EventCategory
 * @returns {Promise<Array>} Array of conflict event objects
 */
export async function fetchUcdpEvents({ limit = 100, category = null } = {}) {
  try {
    const params = new URLSearchParams({ limit })
    if (category) params.set('category', category)

    const res = await fetch(`${API_BASE}/api/ucdp-events?${params}`)
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    return await res.json()
  } catch (err) {
    console.error('[UCDP] Fetch failed:', err)
    return []
  }
}

/**
 * Fetch recent NGA NAVAREA maritime broadcast warnings.
 * @param {number} [limit=50] - Max warnings to return
 * @returns {Promise<Array>} Array of maritime warning objects
 */
export async function fetchNgaWarnings(limit = 50) {
  try {
    const res = await fetch(`${API_BASE}/api/nga-warnings?limit=${limit}`)
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    return await res.json()
  } catch (err) {
    console.error('[NGA] Fetch failed:', err)
    return []
  }
}

/**
 * Fetch the aggregated conflict summary across all sources.
 * Returns { total_events, verified_events, by_source, by_category }
 * @returns {Promise<object>}
 */
export async function fetchConflictSummary() {
  try {
    const res = await fetch(`${API_BASE}/api/conflict/summary`)
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    return await res.json()
  } catch (err) {
    console.error('[ConflictSummary] Fetch failed:', err)
    return { total_events: 0, verified_events: 0, by_source: {}, by_category: {} }
  }
}
