import './Bets.css'
import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import useAuthStore from '../../store/auth'
import api from '../../api/client'

const DDV = '14.24.1'

const STATUS_CONFIG = {
  pending:   { label: 'En cours', color: '#f59e0b', bg: '#f59e0b12', icon: '⏳' },
  won:       { label: 'Gagné',    color: '#22c55e', bg: '#22c55e12', icon: '✓'  },
  lost:      { label: 'Perdu',    color: '#ef4444', bg: '#ef444412', icon: '✗'  },
  cancelled: { label: 'Annulé',  color: '#6b7280', bg: '#6b728012', icon: '—'  },
}

const BET_TYPE_LABELS = {
  who_wins:    '🏆 Victoire',
  first_blood: '🩸 First Blood',
}

const QUEUE_NAMES = {
  '420': 'Ranked Solo',
  '440': 'Ranked Flex',
  '400': 'Normal',
  '450': 'ARAM',
}

function timeAgo(dateStr) {
  if (!dateStr) return ''
  const diff = Date.now() - new Date(dateStr).getTime()
  const h = Math.floor(diff / 3600000)
  const m = Math.floor(diff / 60000)
  if (h > 24) return `il y a ${Math.floor(h / 24)}j`
  if (h > 0)  return `il y a ${h}h`
  if (m > 0)  return `il y a ${m}m`
  return "à l'instant"
}

function champIcon(name) {
  if (!name) return null
  return `https://ddragon.leagueoflegends.com/cdn/${DDV}/img/champion/${name}.png`
}

function groupBetsByGame(bets) {
  const groups = {}
  for (const bet of bets) {
    const key = bet.live_game_id ?? `solo_${bet.id}`
    if (!groups[key]) groups[key] = []
    groups[key].push(bet)
  }

  return Object.values(groups)
    .map(group => {
      const statuses = group.map(b => b.status)
      let globalStatus = 'pending'
      if (statuses.every(s => s === 'won'))         globalStatus = 'won'
      else if (statuses.some(s => s === 'lost'))    globalStatus = 'lost'
      else if (statuses.some(s => s === 'pending')) globalStatus = 'pending'
      else globalStatus = 'cancelled'

      const totalAmount = group.reduce((acc, b) => acc + b.amount, 0)
      const totalPayout = group.reduce((acc, b) => acc + (b.payout || 0), 0)
      const odds = Math.pow(2, group.length)

      return {
        key:          group[0].live_game_id ?? `solo_${group[0].id}`,
        live_game_id: group[0].live_game_id,
        game_status:  group[0].game_status,
        game:         group[0].game,
        bets:         group,
        globalStatus,
        totalAmount,
        totalPayout,
        odds,
        created_at: group[0].created_at,
      }
    })
    .sort((a, b) => new Date(b.created_at) - new Date(a.created_at))
}

export default function Bets() {
  const navigate = useNavigate()
  const { user } = useAuthStore()

  const [bets,    setBets]    = useState([])
  const [loading, setLoading] = useState(true)
  const [filter,  setFilter]  = useState('all')

  useEffect(() => {
    if (!user) { navigate('/login'); return }
    api.get('/bets/my-bets')
      .then(r => setBets(r.data))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [user])

  const tickets = groupBetsByGame(bets)
  const filtered = filter === 'all' ? tickets : tickets.filter(t => t.globalStatus === filter)

  const stats = {
    total:   tickets.length,
    pending: tickets.filter(t => t.globalStatus === 'pending').length,
    won:     tickets.filter(t => t.globalStatus === 'won').length,
    lost:    tickets.filter(t => t.globalStatus === 'lost').length,
    gains:   tickets.filter(t => t.globalStatus === 'won').reduce((acc, t) => acc + t.totalPayout, 0),
  }

  return (
    <div className="bets-page">

      {/* ── HEADER ── */}
      <div className="bets-header">
        <div className="bets-header-inner">
          <div>
            <div className="bets-title">Mes paris</div>
            <div className="bets-sub">Historique de tous tes tickets</div>
          </div>
          <div className="bets-balance">
            <div className="coin-dot" />
            {user?.coins?.toLocaleString()} coins
          </div>
        </div>
      </div>

      <div className="bets-content">

        {/* ── STATS ── */}
        <div className="bets-stats">
          {[
            { icon: '🎯', val: stats.total,                    label: 'Tickets',     color: '#00e5ff', bg: '#00e5ff12' },
            { icon: '⏳', val: stats.pending,                  label: 'En cours',    color: '#f59e0b', bg: '#f59e0b12' },
            { icon: '✓',  val: stats.won,                      label: 'Gagnés',      color: '#22c55e', bg: '#22c55e12' },
            { icon: '✗',  val: stats.lost,                     label: 'Perdus',      color: '#ef4444', bg: '#ef444412' },
            { icon: '🪙', val: stats.gains.toLocaleString(),   label: 'Gains coins', color: '#c89b3c', bg: '#c89b3c12' },
            { icon: '📊', val: `${stats.total > 0 ? Math.round((stats.won / stats.total) * 100) : 0}%`, label: 'Win rate', color: '#d946a8', bg: '#d946a812' },
          ].map((s, i) => (
            <div className="bets-stat-card" key={i}>
              <div className="bst-icon" style={{ background: s.bg }}>{s.icon}</div>
              <div className="bst-val" style={{ color: s.color }}>{s.val}</div>
              <div className="bst-label">{s.label}</div>
            </div>
          ))}
        </div>

        {/* ── FILTRES ── */}
        <div className="bets-filters">
          {[
            { key: 'all',     label: `Tous (${tickets.length})` },
            { key: 'pending', label: `⏳ En cours (${stats.pending})` },
            { key: 'won',     label: `✓ Gagnés (${stats.won})` },
            { key: 'lost',    label: `✗ Perdus (${stats.lost})` },
          ].map(f => (
            <button key={f.key} className={`filter-btn ${filter === f.key ? 'active' : ''}`}
              onClick={() => setFilter(f.key)}>
              {f.label}
            </button>
          ))}
        </div>

        {/* ── LISTE ── */}
        {loading ? (
          <div className="bets-loading">
            <div className="bets-spinner" />
            <span>Chargement de tes paris...</span>
          </div>
        ) : filtered.length === 0 ? (
          <div className="bets-empty">
            <div className="bets-empty-icon">🎯</div>
            <div className="bets-empty-title">Aucun ticket trouvé</div>
            <div className="bets-empty-sub">
              {filter === 'all' ? "Tu n'as pas encore placé de pari." : `Aucun ticket « ${STATUS_CONFIG[filter]?.label} ».`}
            </div>
            {filter === 'all' && (
              <button className="bets-cta" onClick={() => navigate('/')}>
                Voir les parties en direct →
              </button>
            )}
          </div>
        ) : (
          <div className="bets-list">
            {filtered.map((ticket, i) => {
              const status = STATUS_CONFIG[ticket.globalStatus] || STATUS_CONFIG.pending
              const isLive = ticket.game_status === 'live'
              const game   = ticket.game
              const pro    = game?.pro
              const queue  = QUEUE_NAMES[game?.queue] || 'Ranked'

              return (
                <div key={ticket.key} className="ticket-row" style={{ animationDelay: `${i * 0.05}s` }}>

                  {/* Barre colorée gauche */}
                  <div className="ticket-bar" style={{ background: status.color }} />

                  {/* ── GAUCHE : contexte game ── */}
                  <div className="ticket-game-ctx">
                    {/* Badge LIVE ou terminé */}
                    <div className={`ticket-game-badge ${isLive ? 'live' : 'ended'}`}>
                      {isLive ? <><span className="tg-dot" />LIVE</> : 'Terminé'}
                    </div>

                    {/* Pro photo + nom + team */}
                    {pro ? (
                      <div className="ticket-pro">
                        {pro.photo_url
                          ? <img src={pro.photo_url} alt={pro.name} className="ticket-pro-photo"
                              style={{ borderColor: pro.accent_color || '#00e5ff' }} />
                          : <div className="ticket-pro-placeholder" style={{ borderColor: pro.accent_color || '#00e5ff' }}>
                              {pro.name.slice(0, 2).toUpperCase()}
                            </div>
                        }
                        <div>
                          <div className="ticket-pro-name">{pro.name}</div>
                          <div className="ticket-pro-team" style={{ color: pro.accent_color || '#6b7280' }}>
                            {pro.team}
                          </div>
                        </div>
                      </div>
                    ) : (
                      <div className="ticket-pro-unknown">
                        <div className="ticket-pro-placeholder">?</div>
                        <div className="ticket-pro-name" style={{ color: '#6b7280' }}>Partie inconnue</div>
                      </div>
                    )}

                    {/* Queue + date */}
                    <div className="ticket-game-meta">
                      <span className="ticket-queue">{queue}</span>
                      <span className="ticket-date">{timeAgo(ticket.created_at)}</span>
                    </div>
                  </div>

                  {/* ── MILIEU : sélections du ticket ── */}
                  <div className="ticket-body">
                    {ticket.bets.map((bet, j) => {
                      const betStatus  = STATUS_CONFIG[bet.status] || STATUS_CONFIG.pending
                      const betPlayer  = bet.game?.bet_player
                      const champName  = betPlayer?.champion_name
                      const icon       = champIcon(champName)
                      const side       = betPlayer?.side
                      const sideColor  = side === 'blue' ? '#378add' : '#ef4444'

                      return (
                        <div key={j} className="ticket-sel-row">

                          {/* Icône champion */}
                          <div className="ticket-champ-wrap">
                            {icon
                              ? <img src={icon} alt={champName} className="ticket-champ-icon"
                                  onError={e => { e.target.style.display = 'none' }} />
                              : <div className="ticket-champ-placeholder">?</div>
                            }
                            {side && <div className="ticket-side-dot" style={{ background: sideColor }} />}
                          </div>

                          {/* Infos sélection */}
                          <div className="ticket-sel-info">
                            <div className="ticket-sel-type">{BET_TYPE_LABELS[bet.bet_type] || bet.bet_type}</div>
                            <div className="ticket-sel-detail">
                              {bet.bet_type === 'who_wins' && (
                                <span style={{ color: sideColor, fontWeight: 700 }}>
                                  {bet.bet_value === 'blue' ? 'Blue side' : 'Red side'}
                                </span>
                              )}
                              {bet.bet_type === 'first_blood' && champName && (
                                <>
                                  <span style={{ color: '#e8eaf0', fontWeight: 600 }}>{champName}</span>
                                  {betPlayer?.summoner_name && (
                                    <span className="ticket-sel-player"
                                      onClick={() => betPlayer.puuid && navigate(`/player/${betPlayer.region}/${betPlayer.summoner_name}/EUW`)}
                                    >
                                      — {betPlayer.summoner_name}
                                    </span>
                                  )}
                                </>
                              )}
                            </div>
                          </div>

                          {/* Statut individuel si combiné */}
                          {ticket.bets.length > 1 && (
                            <div className="ticket-sel-status" style={{ color: betStatus.color }}>
                              {betStatus.icon}
                            </div>
                          )}

                          <span className="ticket-sel-x">×2</span>
                        </div>
                      )
                    })}
                  </div>

                  {/* ── DROITE : financier + actions ── */}
                  <div className="ticket-right">

                    {/* Infos financières */}
                    <div className="ticket-finances">
                      <div className="ticket-fin-row">
                        <span className="ticket-fin-label">Mise</span>
                        <span className="ticket-fin-val">{ticket.totalAmount.toLocaleString()} <span className="coin-small">coins</span></span>
                      </div>
                      <div className="ticket-fin-row">
                        <span className="ticket-fin-label">Cote</span>
                        <span className="ticket-fin-val" style={{ color: '#c89b3c' }}>×{ticket.odds.toFixed(1)}</span>
                      </div>
                      <div className="ticket-fin-row">
                        <span className="ticket-fin-label">
                          {ticket.globalStatus === 'won' ? 'Gagné' : ticket.globalStatus === 'lost' ? 'Perdu' : 'Potentiel'}
                        </span>
                        <span className="ticket-fin-val" style={{
                          color: ticket.globalStatus === 'won'  ? '#22c55e'
                               : ticket.globalStatus === 'lost' ? '#ef4444'
                               : '#9ca3af'
                        }}>
                          {ticket.globalStatus === 'won'
                            ? `+${ticket.totalPayout.toLocaleString()}`
                            : ticket.globalStatus === 'lost'
                              ? `-${ticket.totalAmount.toLocaleString()}`
                              : `~${Math.floor(ticket.totalAmount * ticket.odds).toLocaleString()}`
                          } <span className="coin-small">coins</span>
                        </span>
                      </div>
                    </div>

                    {/* Boutons */}
                    <div className="ticket-actions">
                      {isLive && ticket.live_game_id && (
                        <button className="ticket-game-btn"
                          onClick={() => navigate(`/game/${ticket.live_game_id}`)}>
                          <span className="ticket-game-live-dot" />
                          Voir la partie
                        </button>
                      )}
                      <div className="ticket-status-badge"
                        style={{ color: status.color, background: status.bg, borderColor: status.color + '30' }}>
                        <span>{status.icon}</span>
                        {status.label}
                      </div>
                    </div>
                  </div>

                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}