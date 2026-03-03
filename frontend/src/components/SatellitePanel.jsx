// Sentinel-2 quicklook viewer panel
// Shown when a VERIFIED event has a satellite quicklook URL attached

export default function SatellitePanel({ event, onClose }) {
  if (!event?.satellite_quicklook) return null

  return (
    <div className="satellite-panel">
      <div className="satellite-panel__header">
        <span className="satellite-panel__title">SENTINEL-2 QUICKLOOK</span>
        <span className="satellite-panel__event-id">EVENT #{event.id}</span>
        <button
          className="satellite-panel__close"
          onClick={onClose}
          aria-label="Close satellite panel"
        >
          ✕
        </button>
      </div>

      <div className="satellite-panel__meta">
        <span>{event.location_name}</span>
        <span className="satellite-panel__verified-badge">
          SENTINEL-2 CONFIRMED
        </span>
      </div>

      <div className="satellite-panel__image-container">
        <img
          className="satellite-panel__image"
          src={event.satellite_quicklook}
          alt={`Sentinel-2 quicklook for event ${event.id}`}
          loading="lazy"
        />
      </div>

      <div className="satellite-panel__footer">
        <span className="satellite-panel__source">
          Source: Copernicus Data Space / ESA
        </span>
        <span className="satellite-panel__resolution">
          Resolution: 10m/px (Band B04/B03/B02)
        </span>
      </div>
    </div>
  )
}
