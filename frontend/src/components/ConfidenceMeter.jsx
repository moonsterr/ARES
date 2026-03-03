// Renders the [Bel, Pl] confidence interval as a segmented bar.
// - Left grey segment: pure ignorance (0 → Bel)
// - Colored segment: committed belief (Bel → Pl)
// - Right grey segment: remaining uncertainty (Pl → 1.0)
// Red warning if conflict_k > 0.4

export default function ConfidenceMeter({ bel, pl, conflictK }) {
  const isConflicted = conflictK > 0.4
  const meterColor   = isConflicted ? '#a855f7' : pl > 0.7 ? '#22c55e' : '#eab308'

  const belPct = Math.max(0, Math.min(100, bel * 100))
  const plPct  = Math.max(0, Math.min(100, pl * 100))
  const rangePct = Math.max(0, plPct - belPct)

  return (
    <div
      className="confidence-meter"
      title={`Bel=${bel.toFixed(2)} Pl=${pl.toFixed(2)} K=${conflictK.toFixed(2)}`}
    >
      <div className="confidence-meter__track">
        {/* Ignorance zone — 0 to Bel */}
        <div
          className="confidence-meter__ignorance"
          style={{ width: `${belPct}%` }}
        />
        {/* Belief zone — Bel to Pl */}
        <div
          className="confidence-meter__belief"
          style={{
            left:            `${belPct}%`,
            width:           `${rangePct}%`,
            backgroundColor: meterColor,
            boxShadow:       `0 0 8px ${meterColor}88`,
          }}
        />
      </div>
      <div className="confidence-meter__labels">
        <span>{belPct.toFixed(0)}%</span>
        <span className={isConflicted ? 'conflict-warn' : ''}>
          {isConflicted ? `K=${conflictK.toFixed(2)}` : `Pl ${plPct.toFixed(0)}%`}
        </span>
      </div>
    </div>
  )
}
