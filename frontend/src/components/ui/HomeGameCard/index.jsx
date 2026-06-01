import './HomeGameCard.css'
import api from '../../../api/client'

const CHAMP_VERSION = '16.9.1'

function getChampIcon(championName) {
  if (!championName || championName === '???' || championName === '??') return null
  const ddUrl = `https://ddragon.leagueoflegends.com/cdn/${CHAMP_VERSION}/img/champion/${championName}.png`
  return `${api.defaults.baseURL}/players/proxy/icon?url=${encodeURIComponent(ddUrl)}`
}

export default function GameCard({ game, onBet }) {
  const {
    pro, timer,
    blue_team = [], red_team = [],
  } = game

  const accentColor = pro?.accent_color || '#65BD62'
  const blueTeam    = blue_team ?? []
  const redTeam     = red_team  ?? []
  const champName   = (p) => p.championName || p.championId || '??'

  if (!pro) return null

  return (
    <div className="homegame-card" onClick={() => onBet?.(game)}>

      {/* ── FACE AVANT ── */}
      <div className="pro-overlay">
        <div
          className="pro-bg"
          style={{ background: `linear-gradient(160deg, ${accentColor}1a 0%, #1a1a1a 65%)` }}
        >
          {pro.team_logo_url && (
            <img className="pro-team-logo" src={pro.team_logo_url} alt={pro.team} referrerPolicy="no-referrer" />
          )}
        </div>

        {pro.photo_url
          ? <img className="pro-photo" src={pro.photo_url} alt={pro.name} referrerPolicy="no-referrer" />
          : (
            <div
              className="pro-initials"
              style={{ background: accentColor + '18', color: accentColor, borderColor: accentColor + '40' }}
            >
              {pro.name.slice(0, 2).toUpperCase()}
            </div>
          )
        }

        {pro.role && (
          <div
            className="pro-role-badge"
            style={{ background: accentColor + '18', color: accentColor, borderColor: accentColor + '30' }}
          >
            {pro.role}
          </div>
        )}

        <div className="pro-info">
          <div className="pro-name">{pro.name}</div>
          {pro.team && <div className="pro-team" style={{ color: accentColor }}>{pro.team}</div>}
        </div>
      </div>

      {/* ── FACE ARRIÈRE : hover ── */}
      <div className="game-info">
        {/* Background */}
        <div className="gi-bg" />
        <div
          className="gi-bg-accent"
          style={{ background: `radial-gradient(ellipse at 50% 100%, ${accentColor} 0%, transparent 70%)` }}
        />

        {/* Header */}
        <div className="gi-header">
          <div className="gi-pro-mini">
            <div className="gi-pro-dot" style={{ background: accentColor }} />
            <span className="gi-pro-name">{pro.name}</span>
            {pro.team && (
              <span className="gi-pro-team" style={{ color: accentColor }}>{pro.team}</span>
            )}
          </div>
          <span className="gi-timer">⏱ {timer}</span>
        </div>

        {/* Arena : champions */}
        <div className="gi-arena">

          {/* Blue side */}
          <div className="gi-row">
            {blueTeam.slice(0, 5).map((p, i) => {
              const name = champName(p)
              const icon = getChampIcon(name)
              const isPro = pro && p.puuid === pro.riot_puuid
              return (
                <div
                  key={i}
                  className={`gi-champ${isPro ? ' gi-champ-pro' : ''}`}
                  style={{
                    borderColor: isPro ? accentColor : '#3a6fa830',
                    boxShadow:   isPro ? `0 0 12px ${accentColor}60` : 'none',
                    animationDelay: `${i * 0.03}s`,
                  }}
                  title={name}
                >
                  {icon
                    ? <img src={icon} alt={name} onError={e => { e.target.style.display = 'none' }} />
                    : <span>{name.slice(0, 2)}</span>
                  }
                </div>
              )
            })}
          </div>

          {/* VS divider */}
          <div className="gi-vs-divider">
            <div className="gi-vs-line" style={{ background: '#3a6fa820' }} />
            <span className="gi-vs-text">VS</span>
            <div className="gi-vs-line" style={{ background: '#b03c3c20' }} />
          </div>

          {/* Red side */}
          <div className="gi-row">
            {redTeam.slice(0, 5).map((p, i) => {
              const name = champName(p)
              const icon = getChampIcon(name)
              return (
                <div
                  key={i}
                  className="gi-champ"
                  style={{ borderColor: '#b03c3c28', animationDelay: `${i * 0.03}s` }}
                  title={name}
                >
                  {icon
                    ? <img src={icon} alt={name} onError={e => { e.target.style.display = 'none' }} />
                    : <span>{name.slice(0, 2)}</span>
                  }
                </div>
              )
            })}
          </div>
        </div>

        {/* CTA */}
        <div className="gi-footer">
          <button
            className="bet-btn"
            style={{
              background: `linear-gradient(135deg, ${accentColor} 0%, ${accentColor}cc 100%)`,
              boxShadow:  `0 4px 20px ${accentColor}45`,
            }}
            onClick={e => { e.stopPropagation(); onBet?.(game) }}
          >
            <span>Voir & Parier</span>
            <span className="bet-btn-arrow">→</span>
          </button>
        </div>
      </div>
    </div>
  )
}