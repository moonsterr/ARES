import { useEffect, useRef, useState, useCallback } from 'react'
import {
  Viewer, Ion, Terrain, Cartesian3, Cartesian2,
  Color, HeightReference, VerticalOrigin, LabelStyle,
  DistanceDisplayCondition, ConstantPositionProperty,
  ConstantProperty, Entity, NearFarScalar,
  ScreenSpaceEventType, CallbackProperty, JulianDate
} from 'cesium'
import 'cesium/Build/Cesium/Widgets/widgets.css'
import '../styles/globe.css'
import { EVENT_COLORS } from '../lib/cesiumColors'

// ── High-confidence pulse animation ──────────────────────────────────
// Creates a CallbackProperty that oscillates pixelSize between base and max
// using a sine wave tied to the real-time clock. Used for RSS + FIRMS verified events.
function makePulseSize(baseSize, maxSize, periodMs = 1800) {
  return new CallbackProperty(() => {
    const t = (Date.now() % periodMs) / periodMs          // 0 → 1
    const factor = 0.5 + 0.5 * Math.sin(t * 2 * Math.PI) // 0 → 1 sine
    return baseSize + (maxSize - baseSize) * factor
  }, false)
}

Ion.defaultAccessToken = import.meta.env.VITE_CESIUM_ION_TOKEN || 'your_cesium_ion_token_here'

// Renders the CesiumJS 3D globe.
// Props:
//   events     — array of ConflictEvent objects from WebSocket
//   onEntitySelect — callback when user clicks an entity
export default function MapContainer({ events, onEntitySelect }) {
  const containerRef = useRef(null)
  const viewerRef    = useRef(null)
  const entityMapRef = useRef(new Map())   // id → Cesium Entity reference
  const [viewerReady, setViewerReady] = useState(false)

  // ── Viewer initialization ─────────────────────────────────────────
  useEffect(() => {
    if (!containerRef.current || viewerRef.current) return

    const viewer = new Viewer(containerRef.current, {
      terrain:               Terrain.fromWorldTerrain(),
      animation:             false,
      timeline:              false,
      baseLayerPicker:       false,
      navigationHelpButton:  false,
      homeButton:            false,
      geocoder:              false,
      sceneModePicker:       false,
      fullscreenButton:      false,
      infoBox:               false,   // disabled — we use custom glassmorphism cards
      selectionIndicator:    false,
    })

    // Dark atmosphere / space style
    viewer.scene.globe.enableLighting = true
    viewer.scene.skyBox.show = true
    viewer.scene.backgroundColor = Color.BLACK
    viewer.scene.globe.baseColor = Color.fromCssColorString('#0a0a0f')

    // Remove Bing logo / credits bar
    viewer.cesiumWidget.creditContainer.style.display = 'none'

    // Click handler → custom info card
    viewer.screenSpaceEventHandler.setInputAction((click) => {
      const picked = viewer.scene.pick(click.position)
      if (picked && picked.id instanceof Entity) {
        const eventData = picked.id.properties?.eventData?.getValue()
        if (eventData) onEntitySelect(eventData)
      }
    }, ScreenSpaceEventType.LEFT_CLICK)

    viewerRef.current = viewer
    setViewerReady(true)

    // Focus Middle East on init
    viewer.camera.setView({
      destination: Cartesian3.fromDegrees(36.0, 29.0, 3_500_000)
    })

    return () => {
      entityMapRef.current.clear()
      if (!viewer.isDestroyed()) viewer.destroy()
      viewerRef.current = null
      setViewerReady(false)
    }
  }, [])

  // ── Entity upsert when events change ─────────────────────────────
  // Re-render ALL events on each change so:
  //   • The initial REST hydration paints every entity at once.
  //   • Subsequent WebSocket arrivals (prepended to front) are also caught.
  useEffect(() => {
    if (!viewerReady || !viewerRef.current || !events.length) return
    const viewer = viewerRef.current
    for (const event of events) {
      upsertEntity(viewer, entityMapRef.current, event)
    }
  }, [events, viewerReady])

  return (
    <div
      ref={containerRef}
      className="cesium-globe"
      aria-label="ARES 3D Conflict Map"
    />
  )
}

// ── Upsert logic — update if entity exists, create if new ────────────
function upsertEntity(viewer, entityMap, event) {
  // Use explicit null/undefined check — 0 is a valid coordinate
  if (event.lon == null || event.lat == null) return
  const id = `event-${event.id}`

  // ── Pin sizing & colour logic ─────────────────────────────────────
  // High-confidence: RSS + FIRMS verified (high_confidence flag OR verified=true + confidence≥0.75)
  const isHighConf = event.high_confidence === true ||
    (event.verified === true && (event.confidence ?? 0) >= 0.75)

  // Verified events get the 'verified' green colour override
  const colorKey = event.verified ? 'verified' : (event.category ?? 'unknown')
  const color = Color.fromCssColorString(EVENT_COLORS[colorKey] ?? '#ff4444')

  // RSS-sourced events get a white outline to distinguish them from Telegram pins
  const isRSS = typeof event.source === 'string' && event.source.startsWith('rss:')
  const outlineColor = isRSS ? Color.WHITE.withAlpha(0.8) : color.withAlpha(0.4)
  const outlineWidth = isRSS ? 2 : 6

  const existing = entityMap.get(id)

  if (existing) {
    existing.position = new ConstantPositionProperty(
      Cartesian3.fromDegrees(event.lon, event.lat, 0)
    )
    if (existing.point) {
      existing.point.color        = new ConstantProperty(color)
      existing.point.outlineColor = new ConstantProperty(outlineColor)
      // If this event was just promoted to high-confidence, start pulsing
      if (isHighConf && !(existing.point.pixelSize instanceof CallbackProperty)) {
        existing.point.pixelSize = makePulseSize(14, 26)
      }
    }
    return
  }

  // Base pin size: larger for high-confidence, normal otherwise
  const basePixelSize = isHighConf ? makePulseSize(14, 26) : 10

  const entity = viewer.entities.add({
    id,
    name: event.category,
    position: Cartesian3.fromDegrees(event.lon, event.lat, 0),

    // ─ Point icon — visible at ALL zoom levels, grows when zoomed in
    point: {
      pixelSize:       basePixelSize,
      color:           color,
      outlineColor:    outlineColor,
      outlineWidth:    outlineWidth,
      heightReference: HeightReference.CLAMP_TO_GROUND,
      // Scale UP as you zoom in (near=1km→2x, far=10000km→0.5x)
      scaleByDistance: new NearFarScalar(1e3, 2.0, 1e7, 0.5),
    },

    // ─ Label: fade IN as you zoom closer, fully visible under 2000km altitude
    label: {
      text:            `[${event.category?.toUpperCase()}]${isRSS ? ' 📡' : ''} ${event.location_name ?? ''}`,
      font:            `${isHighConf ? 12 : 11}px "Courier New", monospace`,
      style:           LabelStyle.FILL_AND_OUTLINE,
      fillColor:       color,
      outlineColor:    Color.BLACK,
      outlineWidth:    isHighConf ? 3 : 2,
      verticalOrigin:  VerticalOrigin.BOTTOM,
      pixelOffset:     new Cartesian2(0, -16),
      distanceDisplayCondition: new DistanceDisplayCondition(0, 2_000_000),
      translucencyByDistance:   new NearFarScalar(1_500_000, 1.0, 2_000_000, 0.0),
    },

    // Attach full event data for click handler retrieval
    properties: { eventData: event },
  })

  entityMap.set(id, entity)
}
