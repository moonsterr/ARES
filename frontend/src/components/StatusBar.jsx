const STATUS_COLORS = {
  open:       '#22c55e',
  connecting: '#eab308',
  closed:     '#ef4444',
  error:      '#ef4444',
}

const STATUS_LABELS = {
  open:       'LIVE',
  connecting: 'CONNECTING',
  closed:     'RECONNECTING',
  error:      'ERROR',
}

export default function StatusBar({ wsStatus, eventCount }) {
  const color = STATUS_COLORS[wsStatus] ?? '#64748b'
  const label = STATUS_LABELS[wsStatus] ?? wsStatus?.toUpperCase()

  return (
    <div className="status-bar">
      <div className="status-bar__brand">
        PROJECT ARES
        <span className="status-bar__brand-sub"> // AUTONOMOUS RECONNAISSANCE &amp; EVENT SYNTHESIS</span>
      </div>

      <div className="status-bar__indicators">
        <div className="status-indicator">
          <span
            className="status-indicator__dot"
            style={{ backgroundColor: color, boxShadow: `0 0 6px ${color}` }}
          />
          <span className="status-indicator__label">WS {label}</span>
        </div>

        <div className="status-indicator">
          <span className="status-indicator__label">
            {eventCount} <span className="status-indicator__sub">EVENTS</span>
          </span>
        </div>

        <div className="status-indicator">
          <span
            className="status-indicator__dot"
            style={{ backgroundColor: '#22c55e', boxShadow: '0 0 6px #22c55e' }}
          />
          <span className="status-indicator__label">ALPHA</span>
        </div>

        <div className="status-indicator">
          <span
            className="status-indicator__dot"
            style={{ backgroundColor: '#3b82f6', boxShadow: '0 0 6px #3b82f6' }}
          />
          <span className="status-indicator__label">BRAVO</span>
        </div>
      </div>
    </div>
  )
}
