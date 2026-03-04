const API_BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

export async function fetchInfrastructure() {
  try {
    const res = await fetch(`${API_BASE}/api/infrastructure`)
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    return await res.json()
  } catch (err) {
    console.error('[Infrastructure] Fetch failed:', err)
    return {
      cables: null,
      pipelines: null,
      ports: null,
      military_bases: null,
    }
  }
}

export async function fetchInfrastructureLayer(layer) {
  try {
    const res = await fetch(`${API_BASE}/api/infrastructure/${layer}`)
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    return await res.json()
  } catch (err) {
    console.error(`[Infrastructure] Fetch ${layer} failed:`, err)
    return null
  }
}
