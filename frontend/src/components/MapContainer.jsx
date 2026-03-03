import { useEffect, useRef, useState } from 'react'
import {
  Viewer, Ion, Terrain, Cartesian3, Cartesian2,
  Color, HeightReference, VerticalOrigin, LabelStyle,
  DistanceDisplayCondition, ConstantPositionProperty,
  ConstantProperty, Entity, NearFarScalar,
  ScreenSpaceEventType
} from 'cesium'
import 'cesium/Build/Cesium/Widgets/widgets.css'
import '../styles/globe.css'
import { EVENT_COLORS } from '../lib/cesiumColors'

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
  const color = Color.fromCssColorString(EVENT_COLORS[event.category] ?? '#ff4444')
  const existing = entityMap.get(id)

  if (existing) {
    existing.position = new ConstantPositionProperty(
      Cartesian3.fromDegrees(event.lon, event.lat, 0)
    )
    if (existing.point) {
      existing.point.color = new ConstantProperty(color)
    }
    return
  }

  const entity = viewer.entities.add({
    id,
    name: event.category,
    position: Cartesian3.fromDegrees(event.lon, event.lat, 0),

    // ─ Point icon — visible at ALL zoom levels, grows when zoomed in
    point: {
      pixelSize:       10,
      color:           color,
      outlineColor:    color.withAlpha(0.4),
      outlineWidth:    6,
      heightReference: HeightReference.CLAMP_TO_GROUND,
      // Scale UP as you zoom in (near=1km→2x, far=10000km→0.5x)
      scaleByDistance: new NearFarScalar(1e3, 2.0, 1e7, 0.5),
      // No distanceDisplayCondition — always visible
    },

    // ─ Label: fade IN as you zoom closer, fully visible under 300km altitude
    label: {
      text:            `[${event.category?.toUpperCase()}] ${event.location_name ?? ''}`,
      font:            '11px "Courier New", monospace',
      style:           LabelStyle.FILL_AND_OUTLINE,
      fillColor:       color,
      outlineColor:    Color.BLACK,
      outlineWidth:    2,
      verticalOrigin:  VerticalOrigin.BOTTOM,
      pixelOffset:     new Cartesian2(0, -16),
      // Visible from ground up to 2000km; fades out beyond 1500km
      distanceDisplayCondition: new DistanceDisplayCondition(0, 2_000_000),
      translucencyByDistance:   new NearFarScalar(1_500_000, 1.0, 2_000_000, 0.0),
    },

    // Attach full event data for click handler retrieval
    properties: { eventData: event },
  })

  entityMap.set(id, entity)
}
