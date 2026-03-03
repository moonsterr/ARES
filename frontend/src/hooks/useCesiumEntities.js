import { useRef, useCallback } from 'react'
import {
  Cartesian3, Color, HeightReference, VerticalOrigin, LabelStyle,
  DistanceDisplayCondition, ConstantPositionProperty, ConstantProperty,
  NearFarScalar, Cartesian2
} from 'cesium'
import { EVENT_COLORS } from '../lib/cesiumColors'

/**
 * Manages Cesium entity upsert operations.
 * Returns an `upsertEntity` function to be called when new events arrive.
 * Keeps an internal map of entity id → Cesium Entity for fast updates.
 */
export function useCesiumEntities(viewerRef) {
  const entityMapRef = useRef(new Map())

  const upsertEntity = useCallback((event) => {
    const viewer = viewerRef.current
    if (!viewer || viewer.isDestroyed()) return
    if (event.lon == null || event.lat == null) return

    const id = `event-${event.id}`
    const color = Color.fromCssColorString(EVENT_COLORS[event.category] ?? '#ff4444')
    const existing = entityMapRef.current.get(id)

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

      point: {
        pixelSize:       10,
        color:           color,
        outlineColor:    color.withAlpha(0.4),
        outlineWidth:    6,
        heightReference: HeightReference.CLAMP_TO_GROUND,
        scaleByDistance: new NearFarScalar(1e3, 2.0, 1e7, 0.5),
        // No distanceDisplayCondition — always visible
      },

      label: {
        text:           `[${event.category?.toUpperCase()}] ${event.location_name ?? ''}`,
        font:           '11px "Courier New", monospace',
        style:          LabelStyle.FILL_AND_OUTLINE,
        fillColor:      color,
        outlineColor:   Color.BLACK,
        outlineWidth:   2,
        verticalOrigin: VerticalOrigin.BOTTOM,
        pixelOffset:    new Cartesian2(0, -16),
        distanceDisplayCondition: new DistanceDisplayCondition(0, 2_000_000),
        translucencyByDistance:   new NearFarScalar(1_500_000, 1.0, 2_000_000, 0.0),
      },

      properties: { eventData: event },
    })

    entityMapRef.current.set(id, entity)
  }, [viewerRef])

  const removeEntity = useCallback((eventId) => {
    const viewer = viewerRef.current
    if (!viewer || viewer.isDestroyed()) return

    const id = `event-${eventId}`
    const entity = entityMapRef.current.get(id)
    if (entity) {
      viewer.entities.remove(entity)
      entityMapRef.current.delete(id)
    }
  }, [viewerRef])

  const clearAll = useCallback(() => {
    const viewer = viewerRef.current
    if (!viewer || viewer.isDestroyed()) return

    entityMapRef.current.forEach((entity) => {
      viewer.entities.remove(entity)
    })
    entityMapRef.current.clear()
  }, [viewerRef])

  return { upsertEntity, removeEntity, clearAll }
}
