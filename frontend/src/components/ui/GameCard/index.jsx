import './GameCard.css'

const ICON_COLORS = ['#00e5ff', '#d946a8', '#c89b3c', '#22c55e', '#ef4444']

export default function GameCard({ game, onBet }) {
  const { pro, blueScore, redScore, timer, queue, region, players = [] } = game
  const accentColor = pro?.accent_color || '#00e5ff'

  if (pro) {
    return (
      <div className="game-card">
        <div className="pro-overlay">
          <div className="pro-bg" style={{ background: `linear-gradient(160deg, ${accentColor}15, #242424)` }}>
            {pro.team_logo_url && (
              <img className="pro-team-logo" src={pro.team_logo_url} alt={pro.team} referrerPolicy="no-referrer" />
            )}
          </div>

          {pro.photo_url ? (
            <img
              className="pro-photo"
              src={pro.photo_url}
              alt={pro.name}
              referrerPolicy="no-referrer"
              onError={e => { e.target.style.display = 'none'; e.target.nextSibling.style.display = 'flex' }}
            />
          ) : null}
          <div className="pro-initials" style={{ display: pro.photo_url ? 'none' : 'flex', background: accentColor + '15', color: accentColor, borderColor: accentColor + '40' }}>
            {pro.name.slice(0, 2).toUpperCase()}
          </div>

          {pro.role && (
            <div className="pro-role-badge" style={{ background: accentColor + '12', color: accentColor, borderColor: accentColor + '20' }}>
              {pro.role}
            </div>
          )}

          <div className="pro-info">
            <div className="pro-name">{pro.name}</div>
            {pro.team && <div className="pro-team" style={{ color: accentColor }}>{pro.team}</div>}
          </div>
        </div>

        <div className="game-info">
          <div className="game-top">
            <div className="game-players">
              {players.map((p, i) => (
                <div key={i} className="player-icon" style={{ background: ICON_COLORS[i % ICON_COLORS.length] + '25', color: ICON_COLORS[i % ICON_COLORS.length] }}>
                  {p.slice(0, 2).toUpperCase()}
                </div>
              ))}
            </div>
            <span className="game-timer">{timer}</span>
          </div>

          <div className="game-vs">
            <div className="team-block">
              <div className="team-name">Blue</div>
              <div className="team-score score-blue">{blueScore}</div>
            </div>
            <div className="vs-sep">vs</div>
            <div className="team-block" style={{ textAlign: 'right' }}>
              <div className="team-name">Red</div>
              <div className="team-score score-red">{redScore}</div>
            </div>
          </div>

          <div className="game-footer">
            <span className="game-queue">{queue} · {region}</span>
            <button className="bet-btn" style={{ background: `linear-gradient(135deg, ${accentColor}, ${accentColor}aa)`, boxShadow: `0 4px 16px ${accentColor}50` }} onClick={e => { e.stopPropagation(); onBet?.(game) }}>
              Parier
            </button>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="game-card-simple">
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
        <div className="game-players" style={{ display: 'flex' }}>
          {players.map((p, i) => (
            <div key={i} className="player-icon" style={{ background: ICON_COLORS[i % ICON_COLORS.length] + '25', color: ICON_COLORS[i % ICON_COLORS.length] }}>
              {p.slice(0, 2).toUpperCase()}
            </div>
          ))}
        </div>
        <span className="game-timer">{timer}</span>
      </div>

      <div className="game-vs" style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
        <div className="team-block">
          <div className="team-name">Blue side</div>
          <div className="team-score score-blue">{blueScore}</div>
        </div>
        <div className="vs-sep">vs</div>
        <div className="team-block" style={{ textAlign: 'right' }}>
          <div className="team-name">Red side</div>
          <div className="team-score score-red">{redScore}</div>
        </div>
      </div>

      <div className="game-footer" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <span className="game-queue">{queue} · {region}</span>
        <button className="bet-btn" style={{ background: 'linear-gradient(135deg, #00e5ff, #00b8cc)', boxShadow: '0 4px 16px #00e5ff50' }} onClick={e => { e.stopPropagation(); onBet?.(game) }}>
          Parier
        </button>
      </div>
    </div>
  )
}