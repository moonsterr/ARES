/**
 * Clustering utility — thin wrapper around Supercluster.
 * Aggregates event markers at low zoom levels to prevent map clutter.
 *
 * Usage:
 *   import { buildIndex, getClusters } from './clustering'
 *
 *   const index = buildIndex(events)
 *   const clusters = getClusters(index, viewport)
 *
 * Each returned cluster object is either:
 *   • A regular event point   → { type: 'event',   data: <original event> }
 *   • A cluster aggregate     → { type: 'cluster',  count, lat, lon, clusterId }
 */
import Supercluster from 'supercluster'

/**
 * Default Supercluster options.
 * radius  — pixel radius for merging points at a given zoom (higher = more aggressive)
 * maxZoom — stop clustering above this zoom level (individual pins show above it)
 */
const DEFAULT_OPTIONS = {
  radius:  60,
  maxZoom: 10,
  minZoom: 0,
  minPoints: 3,  // need at least 3 points before forming a cluster
}

/**
 * Build a Supercluster spatial index from an array of ARES events.
 *
 * @param {Array}  events  - Array of event objects with lat/lon fields
 * @param {object} options - Override Supercluster options
 * @returns {Supercluster} Loaded index ready for getClusters()
 */
export function buildIndex(events, options = {}) {
  const index = new Supercluster({ ...DEFAULT_OPTIONS, ...options })

  // Convert ARES events to GeoJSON features for Supercluster
  const features = events
    .filter(ev => ev.lat != null && ev.lon != null)
    .map(ev => ({
      type:       'Feature',
      geometry:   { type: 'Point', coordinates: [ev.lon, ev.lat] },
      properties: ev,
    }))

  index.load(features)
  return index
}

/**
 * Query the index for the current viewport and return display-ready items.
 *
 * @param {Supercluster} index    - Index built by buildIndex()
 * @param {object}       viewport - { longitude, latitude, zoom, width, height } OR { bbox, zoom }
 * @returns {Array} Mixed array of cluster and event objects
 */
export function getClusters(index, viewport) {
  if (!index) return []

  // Compute bounding box from viewport centre + zoom if not provided directly
  let bbox, zoom

  if (viewport.bbox) {
    bbox = viewport.bbox    // [west, south, east, north]
    zoom = Math.floor(viewport.zoom)
  } else {
    // Rough bbox from centre + zoom (good enough for filtering)
    const { longitude, latitude, zoom: z } = viewport
    const delta = 180 / Math.pow(2, z) * 1.5
    bbox = [longitude - delta, latitude - delta, longitude + delta, latitude + delta]
    zoom = Math.floor(z)
  }

  // Clamp bbox to valid range
  bbox = [
    Math.max(-180, bbox[0]),
    Math.max(-90,  bbox[1]),
    Math.min(180,  bbox[2]),
    Math.min(90,   bbox[3]),
  ]

  const raw = index.getClusters(bbox, zoom)

  return raw.map(feature => {
    const { geometry, properties } = feature

    if (properties.cluster) {
      // This is a cluster aggregate
      return {
        type:      'cluster',
        clusterId: properties.cluster_id,
        count:     properties.point_count,
        lat:       geometry.coordinates[1],
        lon:       geometry.coordinates[0],
      }
    }

    // This is an individual event point
    return {
      type: 'event',
      data: properties,
    }
  })
}

/**
 * Expand a cluster to its children (for click-to-expand behaviour).
 *
 * @param {Supercluster} index     - Index built by buildIndex()
 * @param {number}       clusterId - cluster_id from a cluster object
 * @param {number}       zoom      - Current map zoom
 * @returns {Array} Children — may include nested clusters or individual events
 */
export function expandCluster(index, clusterId, zoom) {
  if (!index) return []
  try {
    return index.getChildren(clusterId)
  } catch {
    return []
  }
}

/**
 * Get the zoom level at which a cluster expands into individual points.
 * Useful for fly-to-zoom on cluster click.
 *
 * @param {Supercluster} index     - Index built by buildIndex()
 * @param {number}       clusterId
 * @returns {number} Expansion zoom level
 */
export function getClusterExpansionZoom(index, clusterId) {
  if (!index) return 12
  try {
    return index.getClusterExpansionZoom(clusterId)
  } catch {
    return 12
  }
}
