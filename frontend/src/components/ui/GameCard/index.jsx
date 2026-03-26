import './GameCard.css'

const CHAMP_VERSION = '14.24.1'

function getChampIcon(championName) {
  if (!championName || championName === '???') return null
  return `https://ddragon.leagueoflegends.com/cdn/${CHAMP_VERSION}/img/champion/${championName}.png`
}

export default function GameCard({ game, onBet }) {
  const {
    pro, blueScore, redScore, timer,
    queue, region, blue_team = [], red_team = [],
  } = game
  const accentColor = pro?.accent_color || '#00e5ff'

  const blueTeam = blue_team ?? []
  const redTeam  = red_team  ?? []

  const champName = (p) => p.championName || p.championId || '??'

  if (pro) {
    return (
      <div className="game-card" onClick={() => onBet?.(game)}>

        {/* ── FACE AVANT : photo du pro ── */}
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

        {/* ── FACE ARRIÈRE : infos de la game au hover ── */}
        <div className="game-info">

          {/* Header : timer + queue */}
          <div className="gi-header">
            <span className="gi-timer">⏱ {timer}</span>
            <span className="gi-queue">{queue}</span>
          </div>

          {/* Draft : champions des deux équipes */}
          <div className="gi-draft">

            {/* Blue side */}
            <div className="gi-side gi-blue">
              <div className="gi-side-label" style={{ color: '#378add' }}>Blue</div>
              <div className="gi-champs">
                {blueTeam.slice(0, 5).map((p, i) => {
                  const name = champName(p)
                  const icon = getChampIcon(name)
                  return (
                    <div key={i} className={`gi-champ ${pro && p.puuid === pro.riot_puuid ? 'gi-champ-pro' : ''}`} style={{ borderColor: '#378add40' }}>
                      {icon
                        ? <img src={icon} alt={name} onError={e => { e.target.style.display='none' }} />
                        : <span>{name.slice(0, 2)}</span>
                      }
                    </div>
                  )
                })}
              </div>
              <div className="gi-score" style={{ color: '#378add' }}>{blueScore}</div>
            </div>

            <div className="gi-vs">VS</div>

            {/* Red side */}
            <div className="gi-side gi-red">
              <div className="gi-side-label" style={{ color: '#ef4444' }}>Red</div>
              <div className="gi-champs">
                {redTeam.slice(0, 5).map((p, i) => {
                  const name = champName(p)
                  const icon = getChampIcon(name)
                  return (
                    <div key={i} className="gi-champ" style={{ borderColor: '#ef444440' }}>
                      {icon
                        ? <img src={icon} alt={name} onError={e => { e.target.style.display='none' }} />
                        : <span>{name.slice(0, 2)}</span>
                      }
                    </div>
                  )
                })}
              </div>
              <div className="gi-score" style={{ color: '#ef4444' }}>{redScore}</div>
            </div>
          </div>

          {/* Footer : bouton parier */}
          <div className="gi-footer">
            <button
              className="bet-btn"
              style={{ background: `linear-gradient(135deg, ${accentColor}, ${accentColor}aa)`, boxShadow: `0 4px 16px ${accentColor}50` }}
              onClick={e => { e.stopPropagation(); onBet?.(game) }}
            >
              Voir & Parier
            </button>
          </div>
        </div>
      </div>
    )
  }

  // ── Carte sans pro (ne devrait plus apparaître après le filtre Home) ──
  return null
}