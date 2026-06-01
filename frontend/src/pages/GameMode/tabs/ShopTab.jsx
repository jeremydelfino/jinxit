export default function ShopTab({ packs, budget, opening, onOpen }) {
  return (
    <div className="gm-content">
      <h2 className="gm-section-title">Packs</h2>
      {packs.length === 0
        ? <div className="gm-empty">Aucun pack disponible.</div>
        : (
          <div className="gm-shop-grid">
            {packs.map(p => (
              <div key={p.id} className="gm-pack">
                <div className="gm-pack-name">{p.name}</div>
                {p.description && <div className="gm-pack-desc">{p.description}</div>}
                <div className="gm-pack-weights">
                  {Object.entries(p.weights).filter(([, w]) => w > 0).map(([range, w]) => (
                    <span key={range} className="gm-pack-w">{range}: {w}%</span>
                  ))}
                </div>
                <button className="gm-btn-primary gm-block"
                  disabled={opening === p.id || budget < p.price_budget}
                  onClick={() => onOpen(p)}>
                  {opening === p.id ? 'Ouverture…' : `Ouvrir · 🪙 ${p.price_budget.toLocaleString()}`}
                </button>
              </div>
            ))}
          </div>
        )}
    </div>
  )
}