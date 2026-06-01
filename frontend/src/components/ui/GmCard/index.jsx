import './GmCard.css'

const ROLE_SHORT = { TOP: 'TOP', JUNGLE: 'JGL', MID: 'MID', ADC: 'BOT', SUPPORT: 'SUP' }
const STATS = [
  ['laning', 'LAN', 'Laning'],
  ['teamfight', 'TF', 'Teamfight'],
  ['vision', 'VIS', 'Vision'],
  ['mechanics', 'MEC', 'Mécaniques'],
  ['stress', 'SF', 'Sang-froid'],
  ['clutch', 'CLU', 'Clutch'],
]

function statClass(v) {
  if (v >= 90) return 'gm-s-elite'
  if (v >= 80) return 'gm-s-good'
  if (v >= 70) return 'gm-s-mid'
  return 'gm-s-low'
}

// Palier de carte (rareté implicite via l'OVR) → couleur de bordure / glow
function tierOf(ovr) {
  if (ovr >= 90) return 'elite'   // or
  if (ovr >= 80) return 'good'    // vert
  return 'base'                   // neutre
}

export default function GmCard({ entry, size = 'md' }) {
  const { ovr = 0, role, ego = 0, nationality, stats = {}, player } = entry || {}
  const name   = player?.name || '—'
  const accent = player?.team_accent || '#c89b3c'
  const logo   = player?.team_logo || null
  const flag   = nationality && nationality.length === 2 ? nationality.toLowerCase() : null
  const tier   = tierOf(ovr)

  return (
    <div
      className={`gm-card gm-card-${size} gm-tier-${tier}`}
      style={{ '--gm-accent': accent }}
    >
      {/* Reflet animé au survol */}
      <span className="gm-card-shine" />

      {/* Bandeau haut : OVR + rôle / logo club + drapeau */}
      <div className="gm-card-top">
        <div className="gm-card-ovrwrap">
          <span className="gm-card-ovr">{ovr || '–'}</span>
          <span className="gm-card-role">{ROLE_SHORT[role] || role}</span>
        </div>
        <div className="gm-card-brand">
          {logo && (
            <img className="gm-card-logo" src={logo} alt="" referrerPolicy="no-referrer"
                 onError={e => { e.target.style.display = 'none' }} />
          )}
          {flag && (
            <img className="gm-card-flag" src={`https://flagcdn.com/w40/${flag}.png`} alt=""
                 loading="lazy" onError={e => { e.target.style.display = 'none' }} />
          )}
        </div>
      </div>

      {/* Photo joueur (héros) */}
      <div className="gm-card-photo">
        <span className="gm-card-photo-glow" />
        {player?.photo_url
          ? <img src={player.photo_url} alt={name} referrerPolicy="no-referrer"
                 onError={e => { e.target.style.display = 'none' }} />
          : <div className="gm-card-photo-ph">{name.slice(0, 2).toUpperCase()}</div>}
        <span className="gm-card-photo-fade" />
      </div>

      {/* Identité */}
      <div className="gm-card-info">
        <div className="gm-card-name">{name}</div>
        <div className="gm-card-sub">
          <span className="gm-card-team">{player?.team_code || ''}</span>
          <span className="gm-card-ego" title={`Ego ${ego}/5`}>
            {[1, 2, 3, 4, 5].map(i => (
              <span key={i} className={`gm-star ${i <= ego ? 'on' : ''}`}>★</span>
            ))}
          </span>
        </div>
      </div>

      {/* Stats */}
      <div className="gm-card-stats">
        {STATS.map(([k, lbl, full]) => (
          <div key={k} className="gm-card-stat" title={full}>
            <span className={`gm-stat-val ${statClass(stats[k] ?? 0)}`}>{stats[k] ?? '–'}</span>
            <span className="gm-stat-lbl">{lbl}</span>
          </div>
        ))}
      </div>
    </div>
  )
}