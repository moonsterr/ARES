import React, { useState, useMemo, useCallback, useRef } from 'react'
import { Map } from 'maplibre-gl'
import { Deck } from '@deck.gl/core'
import { ScatterplotLayer, IconLayer, PathLayer } from '@deck.gl/layers'
import { HeatmapLayer } from '@deck.gl/aggregation-layers'
import { MAP_STYLE, INITIAL_VIEW_STATE, LAYER_CONFIG, LAYER_ORDER } from '../config/mapLayers'
import MapPopup from './MapPopup'

const AIR_CRAFT_ICON = {
  url: 'https://raw.githubusercontent.com/visgl/deck.gl-data/master/website/icon-atlas.png',
  width: 128,
  height: 128,
  anchorY: 64,
  mask: true,
}

const ICON_MAPPING = {
  aircraft: { x: 0, y: 0, width: 128, height: 128, mask: true },
  vessel: { x: 128, y: 0, width: 128, height: 128, mask: true },
  base: { x: 256, y: 0, width: 128, height: 128, mask: true },
  port: { x: 384, y: 0, width: 128, height: 128, mask: true },
}

export default function DeckGLMap({ 
  events = [], 
  aircraft = [], 
  vessels = [],
  hotspots = [],
  infrastructure = {},
  layerVisibility = {},
  onEntitySelect,
}) {
  const mapContainerRef = useRef(null)
  const deckCanvasRef = useRef(null)
  const mapRef = useRef(null)
  const deckRef = useRef(null)
  
  const [popupInfo, setPopupInfo] = useState(null)
  const [viewState, setViewState] = useState(INITIAL_VIEW_STATE)

  const getLayerVisibility = useCallback((layerId) => {
    if (layerId in layerVisibility) return layerVisibility[layerId]
    return LAYER_CONFIG[layerId]?.defaultVisibility ?? true
  }, [layerVisibility])

  const layers = useMemo(() => {
    const result = []

    if (getLayerVisibility('heatmap') && events.length > 0) {
      result.push(
        new HeatmapLayer({
          id: 'heatmap',
          data: events.filter(e => e.lat && e.lon),
          getPosition: d => [d.lon, d.lat],
          getWeight: d => d.confidence || 0.5,
          colorRange: LAYER_CONFIG.heatmap.colorRange,
          intensity: LAYER_CONFIG.heatmap.intensity,
          threshold: LAYER_CONFIG.heatmap.threshold,
          radiusPixels: LAYER_CONFIG.heatmap.radiusPixels,
          aggregation: LAYER_CONFIG.heatmap.aggregation,
        })
      )
    }

    if (getLayerVisibility('cables') && infrastructure.cables) {
      result.push(
        new PathLayer({
          id: 'cables',
          data: infrastructure.cables.features || [],
          getPath: d => d.geometry.coordinates,
          getColor: LAYER_CONFIG.cables.getColor,
          getWidth: LAYER_CONFIG.cables.getWidth,
          widthMinPixels: LAYER_CONFIG.cables.widthMinPixels,
          rounded: LAYER_CONFIG.cables.rounded,
        })
      )
    }

    if (getLayerVisibility('pipelines') && infrastructure.pipelines) {
      result.push(
        new PathLayer({
          id: 'pipelines',
          data: infrastructure.pipelines.features || [],
          getPath: d => d.geometry.coordinates,
          getColor: d => LAYER_CONFIG.pipelines.getColor(d.properties),
          getWidth: LAYER_CONFIG.pipelines.getWidth,
          widthMinPixels: LAYER_CONFIG.pipelines.widthMinPixels,
          rounded: LAYER_CONFIG.pipelines.rounded,
        })
      )
    }

    if (getLayerVisibility('military_bases') && infrastructure.military_bases) {
      result.push(
        new IconLayer({
          id: 'military_bases',
          data: infrastructure.military_bases.features || [],
          getPosition: d => d.geometry.coordinates,
          getIcon: () => 'base',
          getSize: LAYER_CONFIG.military_bases.getSize,
          getColor: LAYER_CONFIG.military_bases.getColor,
          iconMapping: ICON_MAPPING,
          iconAtlas: AIR_CRAFT_ICON.url,
          pickable: true,
          onClick: ({ object }) => {
            if (object) {
              setPopupInfo({
                x: 400,
                y: 300,
                object: { ...object.properties, lat: object.geometry.coordinates[1], lon: object.geometry.coordinates[0] },
              })
            }
          },
        })
      )
    }

    if (getLayerVisibility('ports') && infrastructure.ports) {
      result.push(
        new IconLayer({
          id: 'ports',
          data: infrastructure.ports.features || [],
          getPosition: d => d.geometry.coordinates,
          getIcon: () => 'port',
          getSize: LAYER_CONFIG.ports.getSize,
          getColor: LAYER_CONFIG.ports.getColor,
          iconMapping: ICON_MAPPING,
          iconAtlas: AIR_CRAFT_ICON.url,
          pickable: true,
          onClick: ({ object }) => {
            if (object) {
              setPopupInfo({
                x: 400,
                y: 300,
                object: { ...object.properties, lat: object.geometry.coordinates[1], lon: object.geometry.coordinates[0] },
              })
            }
          },
        })
      )
    }

    if (getLayerVisibility('conflicts')) {
      const conflictEvents = events.filter(e => e.lat && e.lon && e.category !== 'aircraft')
      if (conflictEvents.length > 0) {
        result.push(
          new ScatterplotLayer({
            id: 'conflicts',
            data: conflictEvents,
            getPosition: d => [d.lon, d.lat],
            getFillColor: LAYER_CONFIG.conflicts.getFillColor,
            getLineColor: LAYER_CONFIG.conflicts.getLineColor,
            getRadius: LAYER_CONFIG.conflicts.getRadius,
            radiusMinPixels: 4,
            radiusMaxPixels: 20,
            lineWidthMinPixels: LAYER_CONFIG.conflicts.lineWidthMinPixels,
            pickable: true,
            autoHighlight: true,
            highlightColor: [255, 255, 255, 80],
            onClick: ({ object }) => {
              if (object && onEntitySelect) {
                onEntitySelect(object)
              }
              if (object) {
                setPopupInfo({
                  x: 400,
                  y: 300,
                  object,
                })
              }
            },
          })
        )
      }
    }

    if (getLayerVisibility('hotspots') && hotspots.length > 0) {
      result.push(
        new ScatterplotLayer({
          id: 'hotspots',
          data: hotspots,
          getPosition: d => [d.lon, d.lat],
          getFillColor: LAYER_CONFIG.hotspots.getFillColor,
          getRadius: LAYER_CONFIG.hotspots.getRadius,
          radiusMinPixels: LAYER_CONFIG.hotspots.radiusMinPixels,
          radiusMaxPixels: LAYER_CONFIG.hotspots.radiusMaxPixels,
          getLineColor: LAYER_CONFIG.hotspots.getLineColor,
          lineWidthMinPixels: LAYER_CONFIG.hotspots.lineWidthMinPixels,
          pickable: true,
        })
      )
    }

    if (getLayerVisibility('aircraft') && aircraft.length > 0) {
      result.push(
        new IconLayer({
          id: 'aircraft',
          data: aircraft,
          getPosition: d => [d.lon, d.lat],
          getIcon: () => 'aircraft',
          getSize: LAYER_CONFIG.aircraft.getSize,
          getColor: LAYER_CONFIG.aircraft.getColor,
          getAngle: LAYER_CONFIG.aircraft.getAngle,
          iconMapping: ICON_MAPPING,
          iconAtlas: AIR_CRAFT_ICON.url,
          sizeScale: 1,
          pickable: true,
          onClick: ({ object }) => {
            if (object && onEntitySelect) {
              onEntitySelect(object)
            }
            if (object) {
              setPopupInfo({
                x: 400,
                y: 300,
                object,
              })
            }
          },
        })
      )
    }

    if (getLayerVisibility('vessels') && vessels.length > 0) {
      result.push(
        new IconLayer({
          id: 'vessels',
          data: vessels,
          getPosition: d => [d.lon, d.lat],
          getIcon: () => 'vessel',
          getSize: LAYER_CONFIG.vessels.getSize,
          getColor: LAYER_CONFIG.vessels.getColor,
          iconMapping: ICON_MAPPING,
          iconAtlas: AIR_CRAFT_ICON.url,
          pickable: true,
          onClick: ({ object }) => {
            if (object && onEntitySelect) {
              onEntitySelect(object)
            }
            if (object) {
              setPopupInfo({
                x: 400,
                y: 300,
                object,
              })
            }
          },
        })
      )
    }

    return result
  }, [events, aircraft, vessels, hotspots, infrastructure, getLayerVisibility, onEntitySelect])

  const layerFilter = useCallback(({ layer, environment }) => {
    if (layer.id.startsWith('aircraft') || layer.id.startsWith('vessels') || 
        layer.id.startsWith('conflicts') || layer.id.startsWith('hotspots') ||
        layer.id.startsWith('cables') || layer.id.startsWith('pipelines') ||
        layer.id.startsWith('military_bases') || layer.id.startsWith('ports') ||
        layer.id === 'heatmap') {
      return true
    }
    return false
  }, [])

  const onViewStateChange = useCallback(({ viewState: vs }) => {
    setViewState(vs)
  }, [])

  const onMapLoad = useCallback(() => {
    const deck = new Deck({
      canvas: deckCanvasRef.current,
      width: '100%',
      height: '100%',
      initialViewState: viewState,
      controller: true,
      layers: [],
      onViewStateChange,
      layerFilter,
      getTooltip: ({ object }) => object && {
        html: `<div style="color: white; background: rgba(0,0,0,0.8); padding: 8px; border-radius: 4px;">
          ${object.location_name || object.callsign || object.name || 'Event'}
          ${object.lat ? `<br/>${object.lat.toFixed(4)}, ${object.lon.toFixed(4)}` : ''}
        </div>`,
        style: { backgroundColor: 'transparent', fontSize: '0.8em' }
      },
    })
    
    deckRef.current = deck
    
    const map = new Map({
      container: mapContainerRef.current,
      style: MAP_STYLE,
      center: [INITIAL_VIEW_STATE.longitude, INITIAL_VIEW_STATE.latitude],
      zoom: INITIAL_VIEW_STATE.zoom,
      attributionControl: false,
    })
    
    mapRef.current = map

    map.on('load', () => {
      deck.setProps({
        layers: layers,
      })
    })

    return () => {
      deck.finalize()
      map.remove()
    }
  }, [])

  React.useEffect(() => {
    let deck, map

    const initMap = () => {
      if (mapRef.current || deckRef.current) return

      map = new Map({
        container: mapContainerRef.current,
        style: MAP_STYLE,
        center: [INITIAL_VIEW_STATE.longitude, INITIAL_VIEW_STATE.latitude],
        zoom: INITIAL_VIEW_STATE.zoom,
        attributionControl: false,
      })

      deck = new Deck({
        canvas: deckCanvasRef.current,
        width: '100%',
        height: '100%',
        initialViewState: viewState,
        controller: true,
        layers: [],
        onViewStateChange: ({ viewState: vs }) => {
          setViewState(vs)
          if (mapRef.current) {
            mapRef.current.jumpTo({ center: [vs.longitude, vs.latitude], zoom: vs.zoom })
          }
        },
        layerFilter,
        getTooltip: ({ object }) => object && {
          html: `<div style="color: white; background: rgba(0,0,0,0.8); padding: 8px; border-radius: 4px; font-size: 12px;">
            ${object.location_name || object.callsign || object.name || 'Event'}
            ${object.lat ? `<br/>${object.lat.toFixed(4)}, ${object.lon.toFixed(4)}` : ''}
          </div>`,
          style: { backgroundColor: 'transparent' }
        },
      })

      deckRef.current = deck
      mapRef.current = map
    }

    if (mapContainerRef.current && deckCanvasRef.current) {
      initMap()
    }

    return () => {
      if (deckRef.current) {
        deckRef.current.finalize()
        deckRef.current = null
      }
      if (mapRef.current) {
        mapRef.current.remove()
        mapRef.current = null
      }
    }
  }, [])

  React.useEffect(() => {
    if (deckRef.current) {
      deckRef.current.setProps({ layers })
    }
  }, [layers])

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%' }}>
      <div ref={mapContainerRef} style={{ position: 'absolute', width: '100%', height: '100%' }} />
      <canvas 
        ref={deckCanvasRef} 
        id="deck-canvas"
        style={{ position: 'absolute', width: '100%', height: '100%', pointerEvents: 'auto' }}
      />
      {popupInfo && popupInfo.object && (
        <MapPopup
          object={popupInfo.object}
          onClose={() => setPopupInfo(null)}
        />
      )}
    </div>
  )
}
