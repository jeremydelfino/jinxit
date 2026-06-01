import GmCard from '../../../components/ui/GmCard'
import { ROLES, ROLE_LABEL, SIDES } from '../constants'

export default function SquadTab({ starters, bench, busyId, onPatch, onSell }) {
  const byRole = Object.fromEntries(starters.map(r => [r.role_slot, r]))

  return (
    <div className="gm-content">
      <h2 className="gm-section-title">Composition titulaire</h2>
      <div className="gm-pitch">
        {ROLES.map(role => {
          const r = byRole[role]
          return (
            <div key={role} className="gm-slot">
              <div className="gm-slot-role">{ROLE_LABEL[role]}</div>
              {r ? (
                <>
                  <GmCard entry={r} size="sm" />
                  <div className="gm-side-toggle">
                    {SIDES.map(([val, lbl]) => (
                      <button key={val}
                        className={`gm-side ${r.side === val ? 'on' : ''} gm-side-${val.toLowerCase()}`}
                        disabled={busyId === r.contract_id}
                        onClick={() => onPatch(r.contract_id, { side: val })}>{lbl}</button>
                    ))}
                  </div>
                  <button className="gm-btn-ghost gm-tiny" disabled={busyId === r.contract_id}
                    onClick={() => onPatch(r.contract_id, { is_starter: false })}>Mettre au banc</button>
                </>
              ) : <div className="gm-slot-empty">Vide</div>}
            </div>
          )
        })}
      </div>

      <h2 className="gm-section-title">Réserve <span className="gm-section-count">{bench.length}</span></h2>
      {bench.length === 0
        ? <div className="gm-empty">Aucun joueur en réserve. Ouvre des packs en boutique.</div>
        : (
          <div className="gm-grid">
            {bench.map(r => (
              <div key={r.contract_id} className="gm-bench-item">
                <GmCard entry={r} size="sm" />
                <div className="gm-bench-actions">
                  <button className="gm-btn-mini green" disabled={busyId === r.contract_id}
                    onClick={() => onPatch(r.contract_id, { is_starter: true })}>Titulariser</button>
                  <button className="gm-btn-mini red" disabled={busyId === r.contract_id}
                    onClick={() => onSell(r.contract_id)}>Vendre</button>
                </div>
              </div>
            ))}
          </div>
        )}
    </div>
  )
}