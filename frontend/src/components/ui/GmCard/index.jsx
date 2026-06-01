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

export default function GmCard({ entry, size = 'md' }) {
  const { ovr, role, ego = 0, nationality, stats = {}, player } = entry || {}
  const name = player?.name || '—'

  return (
    <div className={`gm-card gm-card-${size}`}>
      <div className="gm-card-head">
        <div className="gm-card-ovr">{ovr ?? '–'}</div>
        <div className="gm-card-meta">
          <span className="gm-card-role">{ROLE_SHORT[role] || role}</span>
          {nationality && <span className="gm-card-nat">{nationality}</span>}
        </div>
      </div>

      <div className="gm-card-photo">
        {player?.photo_url
          ? <img src={player.photo_url} alt={name} referrerPolicy="no-referrer" onError={e => { e.target.style.display = 'none' }} />
          : <div className="gm-card-photo-ph">{name.slice(0, 2).toUpperCase()}</div>}
      </div>

      <div className="gm-card-name">{name}</div>
      <div className="gm-card-team">{player?.team_code || ''}</div>

      <div className="gm-card-ego" title={`Ego ${ego}/5`}>
        {[1, 2, 3, 4, 5].map(i => (
          <span key={i} className={`gm-star ${i <= ego ? 'on' : ''}`}>★</span>
        ))}
      </div>

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