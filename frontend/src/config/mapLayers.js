import { EVENT_COLORS } from '../lib/cesiumColors'

export const MAP_STYLE = 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json'

export const INITIAL_VIEW_STATE = {
  longitude: 42.5,
  latitude: 30.0,
  zoom: 4,
  pitch: 0,
  bearing: 0,
  minZoom: 2,
  maxZoom: 18,
}

export const MIDDLE_EAST_BOUNDS = {
  west: 25.0,
  south: 14.0,
  east: 65.0,
  north: 42.0,
}

export const LAYER_CONFIG = {
  conflicts: {
    id: 'conflicts',
    label: 'Conflict Events',
    type: 'ScatterplotLayer',
    defaultVisibility: true,
    description: 'Telegram + RSS + GDELT conflict events',
    color: EVENT_COLORS.air_alert,
    radius: 8,
    getRadius: d => d.radius || 8,
    getFillColor: d => {
      if (d.verified) return [34, 197, 94, 200]
      if (d.conflict_k > 0.4) return [168, 85, 247, 200]
      const cat = d.category
      const colors = {
        air_alert: [239, 68, 68, 200],
        ground_strike: [249, 115, 22, 200],
        troop_movement: [59, 130, 246, 200],
        naval_event: [6, 182, 212, 200],
        explosion: [234, 179, 8, 200],
        casualty_report: [232, 121, 249, 200],
        unknown: [148, 163, 184, 200],
      }
      return colors[cat] || colors.unknown
    },
    getLineColor: d => {
      if (d.verified) return [34, 197, 94, 255]
      if (d.conflict_k > 0.4) return [168, 85, 247, 255]
      return [255, 255, 255, 100]
    },
    lineWidthMinPixels: 1,
  },

  heatmap: {
    id: 'heatmap',
    label: 'Event Heatmap',
    type: 'HeatmapLayer',
    defaultVisibility: false,
    description: 'Density visualization of recent events',
    colorRange: [
      [255, 255, 178],
      [254, 204, 92],
      [253, 141, 60],
      [240, 59, 32],
      [189, 0, 38],
    ],
    intensity: 1,
    threshold: 0.05,
    radiusPixels: 30,
    aggregation: 'SUM',
  },

  aircraft: {
    id: 'aircraft',
    label: 'Military Aircraft',
    type: 'IconLayer',
    defaultVisibility: true,
    description: 'ADS-B military aircraft positions',
    iconAtlas: 'https://raw.githubusercontent.com/visgl/deck.gl-data/master/website/icon-atlas.png',
    iconMapping: {
      aircraft: { x: 0, y: 0, width: 128, height: 128, mask: true }
    },
    getIcon: d => 'aircraft',
    getSize: 24,
    getColor: [56, 189, 248, 220],
    getAngle: d => -d.heading || 0,
  },

  vessels: {
    id: 'vessels',
    label: 'Naval Vessels',
    type: 'IconLayer',
    defaultVisibility: true,
    description: 'AIS vessel positions',
    iconAtlas: 'https://raw.githubusercontent.com/visgl/deck.gl-data/master/website/icon-atlas.png',
    iconMapping: {
      vessel: { x: 128, y: 0, width: 128, height: 128, mask: true }
    },
    getIcon: d => 'vessel',
    getSize: 20,
    getColor: [6, 182, 212, 220],
  },

  military_bases: {
    id: 'military_bases',
    label: 'Military Bases',
    type: 'IconLayer',
    defaultVisibility: false,
    description: 'Known military installations',
    iconAtlas: 'https://raw.githubusercontent.com/visgl/deck.gl-data/master/website/icon-atlas.png',
    iconMapping: {
      base: { x: 256, y: 0, width: 128, height: 128, mask: true }
    },
    getIcon: d => 'base',
    getSize: 16,
    getColor: [239, 68, 68, 180],
  },

  ports: {
    id: 'ports',
    label: 'Ports',
    type: 'IconLayer',
    defaultVisibility: false,
    description: 'Major shipping ports',
    iconAtlas: 'https://raw.githubusercontent.com/visgl/deck.gl-data/master/website/icon-atlas.png',
    iconMapping: {
      port: { x: 384, y: 0, width: 128, height: 128, mask: true }
    },
    getIcon: d => 'port',
    getSize: 14,
    getColor: [34, 197, 94, 180],
  },

  cables: {
    id: 'cables',
    label: 'Submarine Cables',
    type: 'PathLayer',
    defaultVisibility: false,
    description: 'Underwater fiber optic cables',
    getColor: [59, 130, 246, 150],
    getWidth: 2,
    widthMinPixels: 1,
    rounded: true,
  },

  pipelines: {
    id: 'pipelines',
    label: 'Pipelines',
    type: 'PathLayer',
    defaultVisibility: false,
    description: 'Oil and gas pipelines',
    getColor: d => {
      if (d.type === 'oil') return [239, 68, 68, 180]
      if (d.type === 'gas') return [34, 197, 94, 180]
      return [234, 179, 8, 180]
    },
    getWidth: 3,
    widthMinPixels: 2,
    rounded: true,
  },

  hotspots: {
    id: 'hotspots',
    label: 'FIRMS Hotspots',
    type: 'ScatterplotLayer',
    defaultVisibility: false,
    description: 'NASA FIRMS thermal detections',
    getFillColor: [249, 115, 22, 150],
    getRadius: 12,
    radiusMinPixels: 4,
    radiusMaxPixels: 20,
    getLineColor: [249, 115, 22, 255],
    lineWidthMinPixels: 1,
  },
}

export const LAYER_ORDER = [
  'heatmap',
  'cables',
  'pipelines',
  'military_bases',
  'ports',
  'conflicts',
  'hotspots',
  'aircraft',
  'vessels',
]
