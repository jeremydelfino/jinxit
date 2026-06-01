export default function GeneralTab({ team, starters, bench, wage, onGoComp }) {
  return (
    <div className="gm-content">
      <div className="gm-cards-row">
        <div className="gm-panel gm-panel-hero">
          <div className="gm-panel-label">Vue d'ensemble</div>
          <div className="gm-hero-ovr">{team.ovr}<span>OVR équipe</span></div>
          <div className="gm-hero-line">{starters.length} titulaires · {bench.length} en réserve</div>
        </div>

        <div className="gm-panel">
          <div className="gm-panel-label">Finances</div>
          <div className="gm-fin-row"><span>Budget</span><b className="gold">🪙 {team.budget.toLocaleString()}</b></div>
          <div className="gm-fin-row"><span>Masse salariale</span><b className="red">−{wage.toLocaleString()} /j</b></div>
          <div className="gm-fin-row"><span>Fans</span><b>{team.fans.toLocaleString()}</b></div>
          <div className="gm-fin-row"><span>Réputation</span><b>{team.reputation}/100</b></div>
        </div>

        <div className="gm-panel">
          <div className="gm-panel-label">Prochain match</div>
          <div className="gm-next-empty">La compétition arrive bientôt.</div>
          <button className="gm-btn-ghost" onClick={onGoComp}>Voir la compétition</button>
        </div>
      </div>
    </div>
  )
}